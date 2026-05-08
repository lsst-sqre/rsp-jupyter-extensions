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

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const justQuit = 'justquit:justquit';
  export const quitLogout = 'quitlogout:quitlogout';
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
      justQuit(app, false, cfg);
    }
  });

  commands.addCommand(CommandIDs.quitLogout, {
    label: 'Exit and Log Out',
    caption: 'Destroy container and log out',
    execute: () => {
      justQuit(app, true, cfg);
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
  logout: boolean,
  cfg: INubladoConfigResponse
): Promise<any> {
  let targetEndpoint = PageConfig.getOption('hubHost');
  // This needs to be changed when we have service discovery working, but
  // this is a good enough guess for now.  If it fails you just get sent
  // back to the Hub rather than the landing page (and logout probably doesn't
  // work).
  if (targetEndpoint.substring(0, 10) === 'http://nb.') {
    targetEndpoint = 'http://' + targetEndpoint.substring(10);
  }
  if (targetEndpoint.substring(0, 11) === 'https://nb.') {
    targetEndpoint = 'https://' + targetEndpoint.substring(11);
  }
  if (logout) {
    targetEndpoint = targetEndpoint + '/logout';
  }
  logMessage(LogLevels.DEBUG, cfg, `final target endpoint: ${targetEndpoint}`);
  try {
    // Lack of await for infoDialog() is intentional.  If we leave the page
    // before the user acknowledges the dialog, that's fine.
    infoDialog(cfg);
  } catch (infoError) {
    logMessage(LogLevels.WARNING, cfg, `quit: infoDialog failed: ${infoError}`);
  }
  try {
    await hubDeleteRequest(app, cfg);
    logMessage(LogLevels.INFO, cfg, 'Quit complete.');
    window.location.replace(targetEndpoint);
    return null;
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `quit: justQuit failed: ${error}`);
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
