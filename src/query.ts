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

import { ServiceManager, ServerConnection } from '@jupyterlab/services';

import { PageConfig } from '@jupyterlab/coreutils';

import { Widget } from '@lumino/widgets';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { IEnvResponse } from './environment';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const rubinquery = 'rubinquery';
}

/**
 * Interface used by the extension
 */
interface IPathContainer {
  path: string;
}

/**
 * Activate the extension.
 */
export function activateRSPQueryExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, null, 'rsp-query...loading');

  const svcManager = app.serviceManager;

  const { commands } = app;

  commands.addCommand(CommandIDs.rubinquery, {
    label: 'Open from portal query URL...',
    caption: 'Open notebook from supplied portal query URL',
    execute: () => {
      rubinportalquery(app, docManager, svcManager, env);
    }
  });

  // Add commands and menu itmes.
  const menu: Menu.IItemOptions = { command: CommandIDs.rubinquery };
  const rubinmenu = new Menu({
    commands
  });
  rubinmenu.title.label = 'Rubin';
  rubinmenu.insertItem(0, menu);
  mainMenu.addMenu(rubinmenu);
  logMessage(LogLevels.INFO, env, 'rsp-query...loaded');
}

class QueryHandler extends Widget {
  constructor() {
    super({ node: Private.createQueryNode() });
    this.addClass('rubin-qh');
  }

  get inputNode(): HTMLInputElement {
    return this.node.getElementsByTagName('input')[0] as HTMLInputElement;
  }

  getValue(): string {
    return this.inputNode.value;
  }
}

function queryDialog(
  manager: IDocumentManager,
  env: IEnvResponse
): Promise<string | (() => void) | null> {
  const options = {
    title: 'Query Value',
    body: new QueryHandler(),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  };
  return showDialog(options).then(result => {
    if (!result) {
      logMessage(LogLevels.DEBUG, env, 'No result from queryDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    logMessage(LogLevels.DEBUG, env, `Result from queryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, env, 'No result.value from queryDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    if (result.button.label === 'CREATE') {
      logMessage(
        LogLevels.DEBUG,
        env,
        `Got result ${result.value} from queryDialog: CREATE`
      );
      return Promise.resolve(result.value);
    }
    logMessage(LogLevels.DEBUG, env, 'Did not get queryDialog: CREATE');
    return new Promise((res, rej) => {
      /* Nothing */
    });
  });
}

/**
 * Make a request to our endpoint to get a pointer to a templated
 *  notebook for a given query
 *
 * @param url - the path for the query extension
 *
 * @param init - The POST + body for the extension
 *
 * @param settings - the settings for the current notebook server.
 *
 * @returns a Promise resolved with the JSON response
 */
function apiRequest(
  url: string,
  init: RequestInit,
  settings: ServerConnection.ISettings
): Promise<IPathContainer> {
  // Fake out URL check in makeRequest
  const newSettings = ServerConnection.makeSettings({
    baseUrl: settings.baseUrl,
    appUrl: settings.appUrl,
    wsUrl: settings.wsUrl,
    init: settings.init,
    token: settings.token,
    Request: settings.Request,
    Headers: settings.Headers,
    WebSocket: settings.WebSocket
  });
  return ServerConnection.makeRequest(url, init, newSettings).then(response => {
    if (response.status !== 200) {
      return response.json().then(data => {
        throw new ServerConnection.ResponseError(response, data.message);
      });
    }
    return response.json();
  });
}

function rubinportalquery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse
): void {
  queryDialog(docManager, env).then(url => {
    logMessage(LogLevels.DEBUG, env, `Query URL is ${url}`);
    if (!url) {
      logMessage(LogLevels.DEBUG, env, 'Query URL was null');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    const body = JSON.stringify({
      type: 'portal',
      value: url
    });
    const endpoint = PageConfig.getBaseUrl() + 'rubin/query';
    const init = {
      method: 'POST',
      body: body
    };
    const settings = svcManager.serverSettings;
    apiRequest(endpoint, init, settings).then(res => {
      const path = res.path;
      docManager.open(path);
    });
    return new Promise((res, rej) => {
      /* Nothing */
    });
  });
}

/**
 * Initialization data for the jupyterlab-lsstquery extension.
 */
const rspQueryExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPQueryExtension,
  id: token.QUERY_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspQueryExtension;

namespace Private {
  /**
   * Create node for query handler.
   */

  export function createQueryNode(): HTMLElement {
    const body = document.createElement('div');
    const qidLabel = document.createElement('label');
    qidLabel.textContent = 'Enter Query Value';
    const name = document.createElement('input');
    body.appendChild(qidLabel);
    body.appendChild(name);
    return body;
  }
}
