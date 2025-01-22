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

import { ServiceManager } from '@jupyterlab/services';

import { PageConfig } from '@jupyterlab/coreutils';

import { Widget } from '@lumino/widgets';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { IEnvResponse } from './environment';
import { apiRequest } from './request';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {

  export const rubinqueryitem = 'rubinqueryitem';
  export const rubinhistory = 'rubinhistory';
  export const rubinquerynb = 'rubinquerynb';
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

  commands.addCommand(CommandIDs.rubinqueryitem, {
    label: 'Open from your query history...',
    caption: 'Open notebook from supplied query jobref ID or URL',
    execute: () => {
      rubintapquery(app, docManager, svcManager, env);
    }
  });
  commands.addCommand(CommandIDs.rubinquerynb, {
    label: 'All queries',
    caption: 'Open notebook requesting all query history',
    execute: () => {
      rubinqueryallhistory(app, docManager, svcManager, env);
    }
  });

  // Add commands and menu itmes.
  const querymenu: Menu.IItemOptions = { command: CommandIDs.rubinqueryitem };
  const rubinmenu = new Menu({
    commands
  });
  const allquerynb: Menu.IItemOptions = { command: CommandIDs.rubinquerynb };
  rubinmenu.title.label = 'Rubin';

  rubinmenu.insertItem(10, querymenu);
  rubinmenu.addItem({ type: "separator" });
  rubinmenu.insertItem(30, allquerynb);

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
    title: 'Query Jobref ID or URL',
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

// function rubinqueryrecenthistory(
//   app: JupyterFrontEnd,
//   docManager: IDocumentManager,
//   svcManager: ServiceManager.IManager,
//   env: IEnvResponse
// ): void {
//   const count = 5
//   const endpoint = PageConfig.getBaseUrl() + `rubin/query/tap/history/${count}`;
//   const init = {
//     method: 'GET',
//   };
//   const settings = svcManager.serverSettings;
//   apiRequest(endpoint, init, settings).then(res => { });
// }

function rubinqueryallhistory(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse
): void {
  const endpoint = PageConfig.getBaseUrl() + 'rubin/query/tap/notebooks/query_all';
  const init = {
    method: 'GET',
  };
  const settings = svcManager.serverSettings;
  apiRequest(endpoint, init, settings).then(res => {
    const path_u = res as unknown;
    const path_c = path_u as IPathContainer;
    const path = path_c.path;
    docManager.open(path);
  });
}

function rubintapquery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse
): void {
  queryDialog(docManager, env).then(val => {
    console.log('Query URL/ID is', val);
    if (!val) {
      console.log('Query URL was null');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    const body = JSON.stringify({
      type: 'tap',
      value: val
    });
    const endpoint = PageConfig.getBaseUrl() + 'rubin/query';
    const init = {
      method: 'POST',
      body: body
    };
    const settings = svcManager.serverSettings;
    apiRequest(endpoint, init, settings).then(res => {
      const r_u = res as unknown;
      const r_p = r_u as IPathContainer;
      const path = r_p.path;
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
    qidLabel.textContent = 'Enter Query Jobref ID or URL';
    const name = document.createElement('input');
    body.appendChild(qidLabel);
    body.appendChild(name);
    return body;
  }
}
