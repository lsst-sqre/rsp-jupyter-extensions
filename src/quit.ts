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
  translator: ITranslator | null
): void {
  logMessage(LogLevels.INFO, null, 'rsp-quit: loading...');

  const { commands } = app;
  const trans = (translator || nullTranslator).load('jupyterlab');

  commands.addCommand(CommandIDs.justQuit, {
    label: trans.__('Autosave and Exit'),
    caption: trans.__('Destroy container'),
    describedBy: {},
    execute: () => {
      justQuit(app, QuitDisposition.Quit, cfg, translator);
    }
  });

  commands.addCommand(CommandIDs.quitLogout, {
    label: trans.__('Autosave, Exit, and Log Out'),
    caption: trans.__('Destroy container and log out'),
    describedBy: {},
    execute: () => {
      justQuit(app, QuitDisposition.Logout, cfg, translator);
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
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<any> {
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
    return null;
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
 * Initialization data for the rspQuit extension.
 */
const rspQuitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPQuitExtension,
  id: token.QUIT_ID,
  description: 'Shut down JupyterLab by communicating with the Hub',
  requires: [IMainMenu],
  optional: [ITranslator],
  autoStart: false
};

export default rspQuitExtension;
