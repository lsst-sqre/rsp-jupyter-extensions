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

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { INubladoConfigResponse } from './config';
import { IRepertoireResponse } from './discovery';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const justQuit = 'justquit:justquit';
  export const saveQuit = 'savequit:savequit';
  export const saveLogout = 'savelogout:savelogout';
}

/**
 * Activate the jupyterhub extension.
 */
export function activateRSPSavequitExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  dsc: IRepertoireResponse,
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-savequit: loading...');

  const { commands } = app;

  commands.addCommand(CommandIDs.justQuit, {
    label: 'Exit Without Saving',
    caption: 'Destroy container',
    execute: async () => {
      await justQuit(app, false, dsc, cfg);
    }
  });

  commands.addCommand(CommandIDs.saveQuit, {
    label: 'Save All and Exit',
    caption: 'Save open notebooks and destroy container',
    execute: async () => {
      await saveAndQuit(app, docManager, false, dsc, cfg);
    }
  });

  commands.addCommand(CommandIDs.saveLogout, {
    label: 'Save All, Exit, and Log Out',
    caption: 'Save open notebooks, destroy container, and log out',
    execute: async () => {
      await saveAndQuit(app, docManager, true, dsc, cfg);
    }
  });

  // Add commands and menu itmes.
  const menu: Menu.IItemOptions[] = [
    { command: CommandIDs.justQuit },
    { command: CommandIDs.saveQuit },
    { command: CommandIDs.saveLogout }
  ];
  // Put it at the bottom of file menu
  const rank = 150;
  mainMenu.fileMenu.addGroup(menu, rank);

  logMessage(LogLevels.INFO, cfg, 'rsp-savequit: ...loaded.');
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
  logMessage(
    LogLevels.DEBUG,
    cfg,
    `savequit: hubRequest URL: ${endpoint} | Settings: ${settings}`
  );
  return await ServerConnection.makeRequest(endpoint, init, settings);
}

async function saveAll(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse
): Promise<any> {
  const promises: Promise<any>[] = [];
  for (const widget of app.shell.widgets('main')) {
    if (widget) {
      const context = docManager.contextForWidget(widget);
      if (context) {
        logMessage(
          LogLevels.DEBUG,
          cfg,
          `Saving context for widget: ${{ id: widget.id }}`
        );
        promises.push(context.save());
      } else {
        logMessage(
          LogLevels.WARNING,
          cfg,
          `No context for widget: ${{ id: widget.id }}`
        );
      }
    }
  }
  logMessage(
    LogLevels.DEBUG,
    cfg,
    'Waiting for all save-document promises to resolve.'
  );
  let r = Promise.resolve(1);
  if (promises) {
    Promise.all(promises);
    r = promises[0];
  }
  return r;
}

async function saveAndQuit(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  logout: boolean,
  dsc: IRepertoireResponse,
  cfg: INubladoConfigResponse
): Promise<any> {
  infoDialog(cfg);
  const retval = Promise.resolve(saveAll(app, docManager, cfg));
  retval.then(res => {
    return justQuit(app, logout, dsc, cfg);
  });
  retval.catch(err => {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `savequit: saveAll failed: ${err.message}`
    );
  });
  logMessage(LogLevels.INFO, cfg, 'savequit: Save and Quit complete.');
  return retval;
}

async function justQuit(
  app: JupyterFrontEnd,
  logout: boolean,
  dsc: IRepertoireResponse,
  cfg: INubladoConfigResponse
): Promise<any> {
  infoDialog(cfg);
  // This should come from an endpoint UI, once we add it to discovery.
  let targetEndpoint = 'https://' + dsc.environment_name;
  if (logout) {
    targetEndpoint = targetEndpoint + '/logout';
  }
  await hubDeleteRequest(app, cfg);
  logMessage(LogLevels.INFO, cfg, 'Quit complete.');
  window.location.replace(targetEndpoint);
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
const rspSavequitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPSavequitExtension,
  id: token.SAVEQUIT_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspSavequitExtension;
