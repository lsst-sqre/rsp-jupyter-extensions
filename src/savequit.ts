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
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-savequit: loading...');

  const { commands } = app;

  commands.addCommand(CommandIDs.justQuit, {
    label: 'Exit Without Saving',
    caption: 'Destroy container',
    execute: () => {
      justQuit(app, false, cfg);
    }
  });

  commands.addCommand(CommandIDs.saveQuit, {
    label: 'Save All and Exit',
    caption: 'Save open notebooks and destroy container',
    execute: () => {
      saveAndQuit(app, docManager, false, cfg);
    }
  });

  commands.addCommand(CommandIDs.saveLogout, {
    label: 'Save All, Exit, and Log Out',
    caption: 'Save open notebooks, destroy container, and log out',
    execute: () => {
      saveAndQuit(app, docManager, true, cfg);
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
  logMessage(LogLevels.DEBUG, cfg, `savequit: hubRequest URL: ${endpoint}`);
  return ServerConnection.makeRequest(endpoint, init, settings);
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
          `Saving context for widget: ${widget.id}`
        );
        promises.push(context.save());
      } else {
        logMessage(
          LogLevels.WARNING,
          cfg,
          `No context for widget: ${widget.id}`
        );
      }
    }
  }
  logMessage(
    LogLevels.DEBUG,
    cfg,
    'Waiting for all save-document promises to resolve.'
  );
  try {
    await Promise.all(promises);
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      cfg,
      `Save-document promise(s) failed: ${error}`
    );
  }
}

async function saveAndQuit(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  logout: boolean,
  cfg: INubladoConfigResponse
): Promise<any> {
  try {
    await saveAll(app, docManager, cfg);
    logMessage(LogLevels.INFO, cfg, 'savequit: all documents saved.');
    return justQuit(app, logout, cfg);
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `savequit: saveAll failed: ${error}`);
  }
}

async function justQuit(
  app: JupyterFrontEnd,
  logout: boolean,
  cfg: INubladoConfigResponse
): Promise<any> {
  await infoDialog(cfg);
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
    await hubDeleteRequest(app, cfg);
    logMessage(LogLevels.INFO, cfg, 'Quit complete.');
    window.location.replace(targetEndpoint);
    return Promise<null>;
  } catch (error) {
    logMessage(LogLevels.WARNING, cfg, `savequit: JustQuit failed: ${error}`);
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
const rspSavequitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPSavequitExtension,
  id: token.SAVEQUIT_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspSavequitExtension;
