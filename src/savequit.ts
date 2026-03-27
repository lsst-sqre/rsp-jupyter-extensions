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
import { IEnvResponse } from './environment';

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
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-savequit: loading...');

  const { commands } = app;

  commands.addCommand(CommandIDs.justQuit, {
    label: 'Exit Without Saving',
    caption: 'Destroy container',
    execute: () => {
      justQuit(app, false, env);
    }
  });

  commands.addCommand(CommandIDs.saveQuit, {
    label: 'Save All and Exit',
    caption: 'Save open notebooks and destroy container',
    execute: () => {
      saveAndQuit(app, docManager, false, env);
    }
  });

  commands.addCommand(CommandIDs.saveLogout, {
    label: 'Save All, Exit, and Log Out',
    caption: 'Save open notebooks, destroy container, and log out',
    execute: () => {
      saveAndQuit(app, docManager, true, env);
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

  logMessage(LogLevels.INFO, env, 'rsp-savequit: ...loaded.');
}

async function hubDeleteRequest(
  app: JupyterFrontEnd,
  env: IEnvResponse
): Promise<Response> {
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;
  const endpoint = PageConfig.getBaseUrl() + 'rubin/hub';
  const init = {
    method: 'DELETE'
  };
  logMessage(
    LogLevels.DEBUG,
    env,
    `savequit: hubRequest URL: ${endpoint} | Settings: ${settings}`
  );
  return ServerConnection.makeRequest(endpoint, init, settings);
}

async function saveAll(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  env: IEnvResponse
): Promise<any> {
  const promises: Promise<any>[] = [];
  for (const widget of app.shell.widgets('main')) {
    if (widget) {
      const context = docManager.contextForWidget(widget);
      if (context) {
        logMessage(
          LogLevels.DEBUG,
          env,
          `Saving context for widget: ${widget.id}`
        );
        promises.push(context.save());
      } else {
        logMessage(
          LogLevels.WARNING,
          env,
          `No context for widget: ${widget.id}`
        );
      }
    }
  }
  logMessage(
    LogLevels.DEBUG,
    env,
    'Waiting for all save-document promises to resolve.'
  );
  try {
    await Promise.all(promises);
  } catch (error) {
    logMessage(
      LogLevels.WARNING,
      env,
      `Save-document promise(s) failed: ${error}`
    );
  }
}

async function saveAndQuit(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  logout: boolean,
  env: IEnvResponse
): Promise<any> {
  try {
    await saveAll(app, docManager, env);
    logMessage(LogLevels.INFO, env, 'savequit: all documents saved.');
    return justQuit(app, logout, env);
  } catch (error) {
    logMessage(LogLevels.WARNING, env, `savequit: saveAll failed: ${error}`);
  }
}

async function justQuit(
  app: JupyterFrontEnd,
  logout: boolean,
  env: IEnvResponse
): Promise<any> {
  await infoDialog(env);
  let targetEndpoint = `${env.EXTERNAL_INSTANCE_URL}`;
  if (logout) {
    targetEndpoint = targetEndpoint + '/logout';
  }
  try {
    await hubDeleteRequest(app, env);
    logMessage(LogLevels.INFO, env, 'Quit complete.');
    window.location.replace(targetEndpoint);
    return Promise<null>;
  } catch (error) {
    logMessage(LogLevels.WARNING, env, `savequit: JustQuit failed: ${error}`);
  }
}

async function infoDialog(env: IEnvResponse): Promise<void> {
  const options = {
    title: 'Redirecting to landing page',
    body: 'JupyterLab cleaning up and redirecting to landing page.',
    buttons: [Dialog.okButton({ label: 'Got it!' })]
  };
  await showDialog(options);
  logMessage(LogLevels.DEBUG, env, 'Info dialog panel displayed');
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
