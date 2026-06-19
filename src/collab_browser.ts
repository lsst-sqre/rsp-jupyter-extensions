import {
  ILayoutRestorer,
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import {
  FileBrowser,
  IFileBrowserFactory,
  FilterFileBrowserModel
} from '@jupyterlab/filebrowser';
import { Drive, ServerConnection } from '@jupyterlab/services';
import { IStateDB } from '@jupyterlab/statedb';
import type { SharedDocumentFactory, Contents } from '@jupyterlab/services';
import { folderIcon } from '@jupyterlab/ui-components';
import { WebsocketProvider } from 'y-websocket';
import type * as Y from 'yjs';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { LogLevels, logMessage } from './logger';

import { YFile, YNotebook } from '@jupyter/ydoc';
import type { DocumentChange, ISharedDocument, YDocument } from '@jupyter/ydoc';

const COLLAB_DRIVE_NAME = 'collab';
const COLLAB_API_ENDPOINT = 'rubin/collab';
const COLLAB_FILEID_PATH = COLLAB_API_ENDPOINT + '/fileid/index';
const COLLAB_ROOM_PATH = COLLAB_API_ENDPOINT + '/collaboration/room';
const COLLAB_BROWSER_ID = 'collab:file-browser';

/**
 * Manages the y-websocket connection for a single /collab document.
 *
 * Lifecycle is tied to the YDocument: the provider is automatically disposed
 * when the document is closed (via YDocument.disposed signal).
 *
 * Construction is synchronous; async work (fileid fetch + WS connect) runs
 * in the background and is exposed through `ready`.
 */
class CollabDocumentProvider {
  private _wsProvider: WebsocketProvider | null = null;
  private _isDisposed = false;

  /**
   * Resolves once the initial YDoc state has synced from the server.
   * Rejects on network or server errors.
   */
  readonly ready: Promise<void>;

  constructor(options: ICollabProviderOptions) {
    // Start async work; errors are caught so a failed connection degrades
    // gracefully (read-only mode) rather than crashing the document open.
    this.ready = this._connect(options).catch(err => {
      console.error('[rubin-collab] YDoc connection failed:', err);
    }) as Promise<void>;
  }

  get isDisposed(): boolean {
    return this._isDisposed;
  }

  dispose(): void {
    if (this._isDisposed) {
      return;
    }
    this._isDisposed = true;
    this._wsProvider?.destroy();
    this._wsProvider = null;
  }
  private async _connect(options: ICollabProviderOptions): Promise<void> {
    // Step 1: Obtain the stable file ID from the /collab fileid service.
    //
    // Uses ServerConnection.makeRequest so the Jupyter auth token is
    // included in the request headers automatically.
    const baseUrl = options.serverSettings.baseUrl.replace(/\/$/, '');
    const indexUrl =
      `${baseUrl}/${COLLAB_FILEID_PATH}?` +
      `path=${encodeURIComponent(options.path)}`;

    const response = await ServerConnection.makeRequest(
      indexUrl,
      { method: 'POST' },
      options.serverSettings
    );
    if (!response.ok) {
      throw new ServerConnection.ResponseError(response);
    }
    const { id } = (await response.json()) as { id: string };

    // Step 2: Construct the room ID.
    //
    // Format: "{file_format}:{file_type}:{file_id}"
    // This must match what YRoomFileAPI.room_id parses on the server:
    //   file_format: passed to ContentsManager.get(format=...)
    //   file_type  : passed to ContentsManager.get(type=...)
    //   file_id    : resolved to a path via LocalFileIdManager.get_path()
    const roomId = `${options.format}:${options.contentType}:${id}`;

    // Step 3: Open the y-websocket connection.
    //
    // y-websocket constructs the final URL as:
    //   serverUrl + (serverUrl.endsWith('/') ? '' : '/') + roomname
    // so we pass the base room path without a trailing slash.
    const wsUrl = options.serverSettings.wsUrl.replace(/\/$/, '');
    const wsRoomBase = `${wsUrl}/${COLLAB_ROOM_PATH}`;
    // Pass the Jupyter token as a query parameter (y-websocket appends
    // params to the URL before upgrading the connection).
    const params: Record<string, string> = {};
    if (options.serverSettings.appendToken && options.serverSettings.token) {
      params['token'] = options.serverSettings.token;
    }

    this._wsProvider = new WebsocketProvider(wsRoomBase, roomId, options.ydoc, {
      params,
      awareness: options.awareness,
      disableBc: true // disable broadcast-channel cross-tab sync
    });

    // Step 4: Wait for the initial sync from the server.
    //
    // The 'sync' event fires once y-websocket has received the server's
    // current document state (sync step 1 + step 2 complete).
    return new Promise<void>((resolve, reject) => {
      const timeoutId = setTimeout(
        () => reject(new Error(`[collab] sync timeout for room ${roomId}`)),
        30_000
      );
      this._wsProvider!.once('sync', (isSynced: boolean) => {
        clearTimeout(timeoutId);
        if (isSynced) {
          resolve();
        } else {
          reject(
            new Error(`[collab] server reported not-synced for room ${roomId}`)
          );
        }
      });
    });
  }
}

interface ICollabProviderOptions {
  /** Local file path within the /collab drive, e.g. "notebooks/demo.ipynb". */
  path: string;
  /** File format: 'json' for notebooks, 'text' for plain files. */
  format: string;
  /** Content type: 'notebook' or 'file'. */
  contentType: string;
  /** The Y.Doc to sync with the server. */
  ydoc: Y.Doc;
  /** Shared awareness object from the YDocument (for cursor / presence). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  awareness: any;
  /** Server connection settings carrying baseUrl, wsUrl, and auth token. */
  serverSettings: ServerConnection.ISettings;
}

// ---------------------------------------------------------------------------
// CollabSharedModelFactory
// ---------------------------------------------------------------------------

/**
 * JupyterLab Contents.ISharedFactory for the /collab drive.
 *
 * JupyterLab calls createNew() each time a collaborative document is opened
 * from the collab drive.  We:
 *   1. Create the appropriate YDocument (YNotebook for notebooks, YFile
 *      for everything else) using the registered documentFactories map.
 *   2. Launch a CollabDocumentProvider as a side-effect, connecting the
 *      YDocument to the /collab y-websocket server.
 *   3. Return the YDocument as ISharedDocument.
 *
 * New document types can be registered via registerDocumentFactory(),
 * mirroring the interface used by the JupyterLab collaboration stack.
 */
class CollabSharedModelFactory implements Contents.ISharedFactory {
  readonly collaborative = true;

  /**
   * Per-content-type factories.
   * Keys are Contents.ContentType values ('notebook', 'file', <E2><80><A6>).
   */
  readonly documentFactories = new Map<
    Contents.ContentType,
    SharedDocumentFactory
  >();

  constructor(private readonly _serverSettings: ServerConnection.ISettings) {
    // Register the two built-in content types.
    this.documentFactories.set('notebook', _opts => new YNotebook());
    this.documentFactories.set('file', _opts => new YFile());
  }

  /**
   * Register a custom document factory for a given content type.
   * Called by extensions that introduce new collaborative document types.
   */
  registerDocumentFactory(
    type: Contents.ContentType,
    factory: SharedDocumentFactory
  ): void {
    this.documentFactories.set(type, factory);
  }

  createNew(
    options: Contents.ISharedFactoryOptions
  ): ISharedDocument | undefined {
    // Honour an explicit opt-out of collaboration.
    if (options.collaborative === false) {
      return undefined;
    }

    // Pick the factory for this content type, falling back to 'file'.
    const factory =
      this.documentFactories.get(options.contentType) ??
      this.documentFactories.get('file');
    if (!factory) {
      return undefined;
    }

    // Create the shared YDocument.  Cast to the concrete YDocument class so
    // we can access ydoc (Y.Doc) and awareness (y-protocols Awareness).
    const sharedDoc = factory(options) as YDocument<DocumentChange>;

    // Launch the WebSocket provider.  It starts its async work immediately
    // and holds its own reference to sharedDoc.ydoc; no further action is
    // needed to keep it alive.
    const provider = new CollabDocumentProvider({
      path: options.path,
      format: options.format ?? 'text',
      contentType: options.contentType,
      ydoc: sharedDoc.ydoc,
      awareness: sharedDoc.awareness,
      serverSettings: this._serverSettings
    });

    // Clean up the WebSocket when the document is closed.
    sharedDoc.disposed.connect(() => provider.dispose());

    return sharedDoc;
  }
}

// ---------------------------------------------------------------------------
// CollabDrive
// ---------------------------------------------------------------------------

/**
 * Drive subclass that carries a sharedModelFactory.
 *
 * JupyterLab's ContentsManager.getSharedModelFactory() first checks
 * contentProviderRegistry.getProvider().sharedModelFactory; when that
 * is undefined (as for the plain RestContentProvider created by Drive),
 * it falls back to drive.sharedModelFactory, which we set here.
 *
 * We subclass Drive rather than setting the property after construction
 * so that TypeScript sees a concrete type without requiring `any` casts.
 */
class CollabDrive extends Drive {
  /** The shared-model factory used for YDoc collaboration. */
  sharedModelFactory: Contents.ISharedFactory;

  constructor(serverSettings: ServerConnection.ISettings) {
    super({
      name: COLLAB_DRIVE_NAME,
      apiEndpoint: COLLAB_API_ENDPOINT,
      serverSettings
    });
    this.sharedModelFactory = new CollabSharedModelFactory(serverSettings);
  }
}

export function activateRSPCollabBrowserExtension(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse,
  restorer: ILayoutRestorer | null,
  stateDB: IStateDB | null
): void {
  if (!cfg.collab_dir) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      'Collab directory is not set; not registering collab browser extension'
    );
    return;
  }
  logMessage(LogLevels.INFO, cfg, 'Registering collab browser extension');

  // ------------------------------------------------------------------
  // 1. Register the custom Drive with the application ContentsManager.
  //
  //    CollabDrive:
  //      - apiEndpoint "rubin/collab": REST CRUD at /rubin/collab/...
  //      - sharedModelFactory: YDoc collaboration for opened documents
  //
  //    After addDrive(), paths of the form "collab:<localPath>" are
  //    dispatched through the collab drive.
  // ------------------------------------------------------------------
  const serverSettings = app.serviceManager.serverSettings;
  const collabDrive = new CollabDrive(serverSettings);
  app.serviceManager.contents.addDrive(collabDrive);

  // ------------------------------------------------------------------
  // 2. Create the file browser widget for the collab drive.
  // ------------------------------------------------------------------
  const collabBrowser = new FileBrowser({
    id: COLLAB_BROWSER_ID,
    model: new FilterFileBrowserModel({
      manager: docManager,
      driveName: COLLAB_DRIVE_NAME,
      // Persist the last-visited folder across page reloads when stateDB
      // is available.  The browser opens at the drive root if stateDB is null.
      state: stateDB ?? undefined
    })
  });

  collabBrowser.title.caption = 'Collaboration Space (/collab)';
  collabBrowser.title.icon = folderIcon;

  // ------------------------------------------------------------------
  // 3. Add to the left sidebar and restore layout state.
  // ------------------------------------------------------------------

  app.shell.add(collabBrowser, 'left', { rank: 200 });

  if (restorer) {
    restorer.add(collabBrowser, COLLAB_BROWSER_ID);
  }

  logMessage(
    LogLevels.INFO,
    cfg,
    `Collab filebrowser Drive "${COLLAB_DRIVE_NAME}" registered. ` +
      `REST:  /${COLLAB_API_ENDPOINT}, ` +
      `YDoc:  /${COLLAB_ROOM_PATH}/<roomId>`
  );
}

/**
 * Initialization data for the tutorials extension.
 */
const rspTutorialsExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPCollabBrowserExtension,
  id: token.COLLAB_ID,
  requires: [IDocumentManager, IFileBrowserFactory],
  optional: [ILayoutRestorer, IStateDB],
  autoStart: false
};

export default rspTutorialsExtension;
