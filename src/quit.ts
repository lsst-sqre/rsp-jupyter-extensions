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
  export const saveQuit = 'savequit:savequit';
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
  docManager: IDocumentManager,
  translator: ITranslator | null
): void {
  logMessage(LogLevels.INFO, null, 'rsp-quit: loading...');

  const { commands } = app;
  const trans = (translator || nullTranslator).load('jupyterlab');
  const autosave = app.hasPlugin('@jupyter-ai-contrib/server-documents:plugin');
  logMessage(LogLevels.INFO, null, `rsp-quit: autosave ${autosave}`);

  if (!autosave) {
    commands.addCommand(CommandIDs.justQuit, {
      label: trans.__('Exit'),
      caption: trans.__('Destroy container'),
      describedBy: {},
      execute: () => {
        justQuit(app, QuitDisposition.Quit, cfg, translator);
      }
    });
  }
  commands.addCommand(CommandIDs.saveQuit, {
    label: trans.__('Save and Exit'),
    caption: trans.__('Save open files and destroy container'),
    describedBy: {},
    execute: () => {
      saveQuit(
        app,
        QuitDisposition.Quit,
        cfg,
        docManager,
        translator,
        autosave
      );
    }
  });

  commands.addCommand(CommandIDs.quitLogout, {
    label: trans.__('Save, Exit and Log Out'),
    caption: trans.__('Save open files, destroy container, and log out'),
    describedBy: {},
    execute: () => {
      saveQuit(
        app,
        QuitDisposition.Logout,
        cfg,
        docManager,
        translator,
        autosave
      );
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

async function saveQuit(
  app: JupyterFrontEnd,
  disposition: QuitDisposition,
  cfg: INubladoConfigResponse,
  docManager: IDocumentManager,
  translator: ITranslator | null,
  autosave: boolean
): Promise<void> {
  if (!autosave) {
    await saveAll(app, docManager, cfg);
  }
  justQuit(app, disposition, cfg, translator);
}

async function justQuit(
  app: JupyterFrontEnd,
  disposition: QuitDisposition,
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
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
    return;
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
  requires: [IMainMenu, IDocumentManager],
  optional: [ITranslator],
  autoStart: false
};

export default rspQuitExtension;
