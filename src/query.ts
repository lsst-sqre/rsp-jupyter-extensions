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

import * as token from './tokens';

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
  docManager: IDocumentManager
): void {
  console.log('rsp-query...loading');

  const svcManager = app.serviceManager;

  const { commands } = app;

  commands.addCommand(CommandIDs.rubinquery, {
    label: 'Open from portal query URL...',
    caption: 'Open notebook from supplied portal query URL',
    execute: () => {
      rubinportalquery(app, docManager, svcManager);
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
  console.log('rsp-query...loaded');
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
  manager: IDocumentManager
): Promise<string | (() => void) | null> {
  const options = {
    title: 'Query Value',
    body: new QueryHandler(),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  };
  return showDialog(options).then(result => {
    if (!result) {
      console.log('No result from queryDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    console.log('Result from queryDialog: ', result);
    if (!result.value) {
      console.log('No result.value from queryDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    if (result.button.label === 'CREATE') {
      console.log('Got result ', result.value, ' from queryDialog: CREATE');
      return Promise.resolve(result.value);
    }
    console.log('Did not get queryDialog: CREATE');
    return new Promise((res, rej) => {
      /* Nothing */
    });
  });
}

function apiRequest(
  url: string,
  init: RequestInit,
  settings: ServerConnection.ISettings
): Promise<IPathContainer> {
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
  svcManager: ServiceManager.IManager
): void {
  queryDialog(docManager).then(url => {
    console.log('Query URL is', url);
    if (!url) {
      console.log('Query URL was null');
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
