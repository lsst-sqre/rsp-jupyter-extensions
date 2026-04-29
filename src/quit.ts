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
import { IRSPEndpointsResponse } from './endpoints';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const justQuit = 'justquit:justquit';
  export const quitLogout = 'quitlogout:quitlogout';
}

class RSPEndpoints implements IRSPEndpointsResponse {
  environment_name: string;
  datasets: { [key: string]: string } = {};
  service: { [key: string]: string } = {};
  ui: { [key: string]: string } = {};

  constructor(inp: IRSPEndpointsResponse) {
    this.environment_name = inp.environment_name;
    for (const dsname in inp.datasets) {
      if (inp.datasets[dsname] !== null && inp.datasets[dsname].length !== 0) {
        this.datasets[dsname] = inp.datasets[dsname];
      }
    }
    for (const svcname in inp.service) {
      if (inp.service[svcname] !== null && inp.service[svcname].length !== 0) {
        this.service[svcname] = inp.service[svcname];
      }
    }
    for (const uiname in inp.ui) {
      if (inp.ui[uiname] !== null && inp.ui[uiname].length !== 0) {
        this.ui[uiname] = inp.ui[uiname];
      }
    }
  }
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

async function endpointRequest(
  app: JupyterFrontEnd,
  cfg: INubladoConfigResponse
): Promise<Response> {
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;
  const endpoint = PageConfig.getBaseUrl() + 'rubin/endpoints';
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.DEBUG, cfg, `exit: endpoints URL: ${endpoint}`);
  return ServerConnection.makeRequest(endpoint, init, settings);
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
  try {
    // We don't want to await infoDialog(); if the user fails to acknowledge
    // the dialog before we navigate away, that's OK.
    infoDialog(cfg);
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `exit: infoDialog() failed: ${error}`
    );
  }
  try {
    const res = await endpointRequest(app, cfg);
    const ep_c = res as unknown as IRSPEndpointsResponse;
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Got query history response: ${JSON.stringify(ep_c, undefined, 2)}`
    );
    const ep = new RSPEndpoints(ep_c);

    let targetEndpoint = PageConfig.getOption('hubHost');
    targetEndpoint = ep.ui['landing_page'];
    if (disposition === ExitDisposition.Logout) {
      targetEndpoint = ep.ui['logout'];
    }
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `final target endpoint: ${targetEndpoint}`
    );
    try {
      await hubDeleteRequest(app, cfg);
      logMessage(LogLevels.INFO, cfg, 'Quit complete.');
      window.location.replace(targetEndpoint);
      return Promise<null>;
    } catch (error) {
      logMessage(LogLevels.WARNING, cfg, `exit: exit failed: ${error}`);
    }
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `exit: finding endpoints failed: ${error}`
    );
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
