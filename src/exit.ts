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
  export const exit = 'exit:exit';
  export const logout = 'logout:logout';
}

enum ExitDisposition {
  LandingPage = 'LANDING_PAGE',
  Logout = 'LOGOUT'
}

/**
 * Activate the jupyterhub extension.
 */
export function activateRSPExitExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-exit: loading...');

  const { commands } = app;

  commands.addCommand(CommandIDs.exit, {
    label: 'Exit',
    caption: 'Destroy container',
    execute: () => {
      exit(app, ExitDisposition.LandingPage, cfg);
    }
  });

  commands.addCommand(CommandIDs.logout, {
    label: 'Exit and Log Out',
    caption: 'Destroy container and log out',
    execute: () => {
      exit(app, ExitDisposition.Logout, cfg);
    }
  });

  // Add commands and menu itmes.
  const menu: Menu.IItemOptions[] = [
    { command: CommandIDs.exit },
    { command: CommandIDs.logout }
  ];
  // Put it at the bottom of file menu
  const rank = 150;
  mainMenu.fileMenu.addGroup(menu, rank);

  logMessage(LogLevels.INFO, cfg, 'rsp-exit: ...loaded.');
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
  logMessage(LogLevels.DEBUG, cfg, `exit: hubRequest URL: ${endpoint}`);
  return ServerConnection.makeRequest(endpoint, init, settings);
}

async function exit(
  app: JupyterFrontEnd,
  disposition: ExitDisposition,
  cfg: INubladoConfigResponse
): Promise<any> {
  await infoDialog(cfg);
  let targetEndpoint = PageConfig.getOption('hubHost');
  targetEndpoint = cfg.endpoint.landing_page;
  if (disposition === ExitDisposition.Logout) {
    targetEndpoint = cfg.endpoint.logout;
  }
  logMessage(LogLevels.DEBUG, cfg, `final target endpoint: ${targetEndpoint}`);
  try {
    await hubDeleteRequest(app, cfg);
    logMessage(LogLevels.INFO, cfg, 'Quit complete.');
    window.location.replace(targetEndpoint);
    return Promise<null>;
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
 * Initialization data for the rspSavequit extension.
 */
const rspExitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExitExtension,
  id: token.SAVEQUIT_ID,
  requires: [IMainMenu],
  autoStart: false
};

export default rspExitExtension;
