import {
  ILayoutRestorer,
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { FileBrowser, FilterFileBrowserModel } from '@jupyterlab/filebrowser';
import { Drive } from '@jupyterlab/services';
import { folderIcon } from '@jupyterlab/ui-components';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { LogLevels, logMessage } from './logger';

const DRIVE_NAME = 'collab';
const SIDEBAR_ID = 'jp-collab-filebrowser';

export async function activateRSPCollabBrowserExtension(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse,
  restorer: ILayoutRestorer | null
): Promise<void> {
  if (!cfg.collab_dir) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      'Collab directory is not set; not registering collab browser extension'
    );
    return;
  }
  const drive = new Drive({
    name: DRIVE_NAME,
    serverSettings: app.serviceManager.serverSettings,
    apiEndpoint: 'rubin/collab'
  });
  app.serviceManager.contents.addDrive(drive);

  const model = new FilterFileBrowserModel({
    manager: docManager,
    driveName: drive.name,
    refreshInterval: 10000
  });

  const browser = new FileBrowser({
    id: SIDEBAR_ID,
    model
  });
  browser.title.icon = folderIcon;
  browser.title.caption = `Collab File Browser (${cfg.collab_dir})`;
  browser.node.setAttribute('role', 'region');
  browser.node.setAttribute('aria-label', 'RSP Collab Browser');
  app.shell.add(browser, 'left', { rank: 42069, type: 'RSP Collab Browser' });
  if (restorer) {
    restorer.add(browser, SIDEBAR_ID);
  }
  await app.serviceManager.ready;
  try {
    await model.cd(cfg.collab_dir);
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `[collab-browser] failed to cd ${cfg.collab_dir}: ${error}`
    );
  }
}

/**
 * Initialization data for the tutorials extension.
 */
const rspTutorialsExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPCollabBrowserExtension,
  id: token.COLLAB_ID,
  requires: [IDocumentManager],
  autoStart: false
};

export default rspTutorialsExtension;
