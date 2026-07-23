// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import { Menu } from '@lumino/widgets';

import { showDialog, Dialog } from '@jupyterlab/apputils';

import { IMainMenu } from '@jupyterlab/mainmenu';

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { PageConfig } from '@jupyterlab/coreutils';

import { ServerConnection } from '@jupyterlab/services';

import { ITranslator, nullTranslator } from '@jupyterlab/translation';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { getServiceInfo } from './serviceinfo';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const justQuit = 'justquit:justquit';
  export const saveQuit = 'savequit:savequit';
  export const quitLogout = 'quitlogout:quitlogout';
}

enum QuitDisposition {
  Quit = 'QUIT',
  Logout = 'LOGOUT'
}

/**
 * Activate the jupyterhub extension.
 */
export function activateRSPQuitExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  cfg: INubladoConfigResponse,
  docManager: IDocumentManager,
  translator: ITranslator | null
): void {
  logMessage(LogLevels.INFO, null, 'rsp-quit: loading...');

  const { commands } = app;
  const trans = (translator || nullTranslator).load('jupyterlab');
  const autosave = app.hasPlugin('@jupyter-ai-contrib/server-documents:plugin');
  logMessage(LogLevels.INFO, null, `...autosave ${autosave}...`);

  // Plain exit: destroy the container. Under autosave the server has already
  // persisted open documents, so this reads "Autosave and Exit"; without
  // autosave it is a deliberate quit-without-saving, hence just "Exit".
  commands.addCommand(CommandIDs.justQuit, {
    label: autosave ? trans.__('Autosave and Exit') : trans.__('Exit'),
    caption: trans.__('Destroy container'),
    describedBy: {},
    execute: () => {
      justQuit(app, QuitDisposition.Quit, cfg, translator);
    }
  });

  // "Save and Exit" runs saveAll first, so it is only meaningful when there
  // is no server-side autosave.  That's gated on whether the
  // @jupyter-ai-contrib/server-documents is loaded (server-documents
  // brings in autosave and disables manual saving).
  if (!autosave) {
    commands.addCommand(CommandIDs.saveQuit, {
      label: trans.__('Save and Exit'),
      caption: trans.__('Save open files and destroy container'),
      describedBy: {},
      execute: () => {
        saveQuit(
          app,
          QuitDisposition.Quit,
          cfg,
          docManager,
          translator,
          autosave
        );
      }
    });
  }

  commands.addCommand(CommandIDs.quitLogout, {
    label: autosave
      ? trans.__('Autosave, Exit, and Log Out')
      : trans.__('Save, Exit, and Log Out'),
    caption: autosave
      ? trans.__('Destroy container and log out')
      : trans.__('Save open files, destroy container, and log out'),
    describedBy: {},
    execute: () => {
      saveQuit(
        app,
        QuitDisposition.Logout,
        cfg,
        docManager,
        translator,
        autosave
      );
    }
  });

  // Add commands and menu itmes.
  const menu: Menu.IItemOptions[] = autosave
    ? [{ command: CommandIDs.justQuit }, { command: CommandIDs.quitLogout }]
    : [
        { command: CommandIDs.justQuit },
        { command: CommandIDs.saveQuit },
        { command: CommandIDs.quitLogout }
      ];
  // Put it at the bottom of file menu
  const rank = 150;
  mainMenu.fileMenu.addGroup(menu, rank);

  logMessage(LogLevels.INFO, cfg, 'rsp-quit: ...loaded.');
}

async function hubDeleteRequest(
  app: JupyterFrontEnd,
  cfg: INubladoConfigResponse
): Promise<Response> {
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;
  const endpoint = PageConfig.getBaseUrl() + 'rubin/hub';
  const init = {
    method: 'DELETE'
  };
  logMessage(LogLevels.DEBUG, cfg, `quit: hubRequest URL: ${endpoint}`);
  return ServerConnection.makeRequest(endpoint, init, settings);
}

/**
 * Save every open document. Returns true if all saves succeeded, false if
 * any failed.  The user must then decide whether it is safe to proceed
 * with destroying the container.
 */
async function saveAll(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse
): Promise<boolean> {
  // Each save resolves to true on success or false on failure, so that one
  // failed save neither hides the others nor aborts them mid-flight.
  const promises: Promise<boolean>[] = [];
  for (const widget of app.shell.widgets('main')) {
    if (widget) {
      const context = docManager.contextForWidget(widget);
      if (context) {
        if (!context.model.dirty || context.model.readOnly) {
          // Nothing to persist (clean) or nothing we can persist (read-only);
          // skip it rather than issuing a needless save.
          logMessage(
            LogLevels.DEBUG,
            cfg,
            `Skipping save for widget ${widget.id} (dirty=${context.model.dirty}, readOnly=${context.model.readOnly})`
          );
          continue;
        }
        logMessage(
          LogLevels.DEBUG,
          cfg,
          `Saving context for widget: ${widget.id}`
        );
        promises.push(
          context.save().then(
            () => true,
            error => {
              logMessage(
                LogLevels.WARNING,
                cfg,
                `Save failed for widget ${widget.id}: ${error}`
              );
              return false;
            }
          )
        );
      } else {
        logMessage(LogLevels.DEBUG, cfg, `No context for widget: ${widget.id}`);
      }
    }
  }
  logMessage(
    LogLevels.DEBUG,
    cfg,
    'Waiting for all save-document promises to resolve.'
  );
  const results = await Promise.all(promises);
  return results.every(ok => ok);
}

async function saveQuit(
  app: JupyterFrontEnd,
  disposition: QuitDisposition,
  cfg: INubladoConfigResponse,
  docManager: IDocumentManager,
  translator: ITranslator | null,
  autosave: boolean
): Promise<void> {
  if (!autosave) {
    const saved = await saveAll(app, docManager, cfg);
    if (!saved) {
      // Saving failed: don't silently destroy the container and lose the
      // user's work. Let them decide whether to quit anyway.
      const proceed = await saveFailedDialog(cfg, translator);
      if (!proceed) {
        logMessage(
          LogLevels.INFO,
          cfg,
          'Quit aborted after save failure at user request.'
        );
        return;
      }
      logMessage(
        LogLevels.WARNING,
        cfg,
        'Proceeding with quit despite save failure at user request.'
      );
    }
  }
  await justQuit(app, disposition, cfg, translator);
}

async function justQuit(
  app: JupyterFrontEnd,
  disposition: QuitDisposition,
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
  // Don't await infoDialog(): if we navigate away before the user
  // acknowledges, that's OK.
  try {
    infoDialog(cfg, translator);
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `Exit dialog failed: ${error}`);
    // Don't rethrow - this is a non-critical background operation
  }
  let targetEndpoint = '/';
  try {
    const si = await getServiceInfo(app);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Got serviceinfo response: ${JSON.stringify(si, undefined, 2)}`
    );
    targetEndpoint = si.ui['squareone'];
    if (disposition === QuitDisposition.Logout) {
      targetEndpoint = si.ui['logout'];
    }
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `exit: finding serviceinfo failed: ${error}`
    );
    // Just redirect to root (which will be SquareOne or Hub spawner,
    // depending on whether user domains are in play or not).
  }
  logMessage(LogLevels.DEBUG, cfg, `final target endpoint: ${targetEndpoint}`);
  try {
    await hubDeleteRequest(app, cfg);
    logMessage(LogLevels.INFO, cfg, 'Quit complete.');
    window.location.replace(targetEndpoint);
    return;
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `exit: exit failed: ${error}`);
  }
}

async function infoDialog(
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
  const trans = (translator || nullTranslator).load('jupyterlab');
  const options = {
    title: trans.__('Redirecting to landing page'),
    body: trans.__('JupyterLab cleaning up and redirecting to landing page.'),
    buttons: [Dialog.okButton({ label: trans.__('Got it!') })]
  };
  await showDialog(options);
  logMessage(LogLevels.DEBUG, cfg, 'Info dialog panel displayed');
}

/**
 * Warn the user that one or more documents failed to save, and ask whether
 * they want to quit anyway (losing those changes) or cancel the quit.
 * Returns true if the user chose to proceed with quitting.
 */
async function saveFailedDialog(
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<boolean> {
  const trans = (translator || nullTranslator).load('jupyterlab');
  const options = {
    title: trans.__('Some files could not be saved'),
    body: trans.__(
      'One or more open documents failed to save. If you exit now, ' +
        'those unsaved changes will be lost. Exit anyway?'
    ),
    buttons: [
      Dialog.cancelButton({ label: trans.__('Cancel') }),
      Dialog.warnButton({ label: trans.__('Exit without saving') })
    ]
  };
  const result = await showDialog(options);
  logMessage(
    LogLevels.DEBUG,
    cfg,
    `Save-failed dialog result: accepted=${result.button.accept}`
  );
  return result.button.accept;
}

/**
 * Initialization data for the rspQuit extension.
 */
const rspQuitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPQuitExtension,
  id: token.QUIT_ID,
  description: 'Shut down JupyterLab by communicating with the Hub',
  requires: [IMainMenu, IDocumentManager],
  optional: [ITranslator],
  autoStart: false
};

export default rspQuitExtension;
