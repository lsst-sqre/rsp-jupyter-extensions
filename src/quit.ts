// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import { Menu } from '@lumino/widgets';

import { showDialog, Dialog } from '@jupyterlab/apputils';

import { IMainMenu } from '@jupyterlab/mainmenu';

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { PageConfig } from '@jupyterlab/coreutils';

import { ServerConnection } from '@jupyterlab/services';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { getServiceInfo } from './serviceinfo';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const justQuit = 'justquit:justquit';
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
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-quit: loading...');

  const { commands } = app;

  commands.addCommand(CommandIDs.justQuit, {
    label: 'Exit',
    caption: 'Destroy container',
    execute: () => {
      justQuit(app, QuitDisposition.Quit, cfg);
    }
  });

  commands.addCommand(CommandIDs.quitLogout, {
    label: 'Exit and Log Out',
    caption: 'Destroy container and log out',
    execute: () => {
      justQuit(app, QuitDisposition.Logout, cfg);
    }
  });

  // Add commands and menu itmes.
  const menu: Menu.IItemOptions[] = [
    { command: CommandIDs.justQuit },
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

async function justQuit(
  app: JupyterFrontEnd,
  disposition: QuitDisposition,
  cfg: INubladoConfigResponse
): Promise<any> {
  // Don't await infoDialog(): if we navigate away before the user
  // acknowledges, that's OK.
  try {
    infoDialog(cfg);
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
    return null;
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `exit: exit failed: ${error}`);
  }
}

async function infoDialog(cfg: INubladoConfigResponse): Promise<void> {
  const options = {
    title: 'Redirecting to landing page',
    body: 'JupyterLab cleaning up and redirecting to landing page.',
    buttons: [Dialog.okButton({ label: 'Got it!' })]
  };
  await showDialog(options);
  logMessage(LogLevels.DEBUG, cfg, 'Info dialog panel displayed');
}

/**
 * Initialization data for the rspQuit extension.
 */
const rspQuitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPQuitExtension,
  id: token.QUIT_ID,
  requires: [IMainMenu],
  autoStart: false
};

export default rspQuitExtension;
