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
  export const exit = 'exit:exit';
  export const logout = 'logout:logout';
}

enum ExitDisposition {
  LandingPage = 'LANDING_PAGE',
  Logout = 'LOGOUT'
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
  logMessage(LogLevels.DEBUG, cfg, `exit: hubRequest URL: ${endpoint}`);
  return ServerConnection.makeRequest(endpoint, init, settings);
}

async function exit(
  app: JupyterFrontEnd,
  disposition: ExitDisposition,
  cfg: INubladoConfigResponse
): Promise<any> {
  await infoDialog(cfg);
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
 * Initialization data for the rspSavequit extension.
 */
const rspExitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExitExtension,
  id: token.SAVEQUIT_ID,
  requires: [IMainMenu],
  autoStart: false
};

export default rspExitExtension;
