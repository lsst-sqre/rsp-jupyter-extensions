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

interface IRecentQueryResponse {
  jobref: string;
  text: string;
}

class RecentQueryResponse implements IRecentQueryResponse {
  jobref: string;
  text: string;

  constructor(inp: IRecentQueryResponse) {
    (this.jobref = inp.jobref), (this.text = inp.text);
  }
}

const RECENTQUERIESINDEX = 50; // Arbitrary

/**
 * Activate the extension.
 */
export function activateRSPQueryExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  env: IEnvResponse
): void {
  logMessage(LogLevels.INFO, env, 'rsp-query...loading');

  const svcManager = app.serviceManager;
  const { commands } = app;
  const rubinmenu = new Menu({
    commands
  });

  commands.addCommand(CommandIDs.rubinqueryitem, {
    label: 'Open from your query history...',
    caption: 'Open notebook from supplied query jobref ID or URL',
    execute: () => {
      rubintapquery(app, docManager, svcManager, env, rubinmenu);
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
  const allquerynb: Menu.IItemOptions = { command: CommandIDs.rubinquerynb };
  rubinmenu.title.label = 'Rubin';

  rubinmenu.insertItem(10, querymenu);
  rubinmenu.insertItem(20, { type: 'separator' });
  rubinmenu.insertItem(30, allquerynb);
  rubinmenu.insertItem(40, { type: 'separator' });

  replaceRecentQueriesMenu(app, docManager, svcManager, env, rubinmenu).then(
    () => {
      logMessage(LogLevels.INFO, env, 'recent queries loaded');
    }
  );
  mainMenu.addMenu(rubinmenu);
  logMessage(LogLevels.INFO, env, 'rsp-query...loaded');
}

async function replaceRecentQueriesMenu(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  rubinmenu: Menu
): Promise<void> {
  const recentquerymenu = await getRecentQueryMenu(
    app,
    docManager,
    svcManager,
    env,
    rubinmenu
  );
  logMessage(
    LogLevels.INFO,
    env,
    `querymenu retrieved; removing item at ${RECENTQUERIESINDEX}`
  );
  rubinmenu.removeItemAt(RECENTQUERIESINDEX);
  logMessage(
    LogLevels.INFO,
    env,
    `inserting querymenu at ${RECENTQUERIESINDEX}`
  );
  rubinmenu.insertItem(RECENTQUERIESINDEX,
    {
      type: 'submenu',
      submenu: recentquerymenu
    }
  );
  logMessage(LogLevels.INFO, env, 'inserted querymenu');
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

async function queryDialog(env: IEnvResponse): Promise<string | void> {
  const options = {
    title: 'Query Jobref ID or URL',
    body: new QueryHandler(),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, env, 'No result from queryDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, env, `Result from queryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, env, 'No result.value from queryDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, env, 'No result.button from queryDialog');
      return;
    }
    if (result.button.label === 'CREATE') {
      logMessage(
        LogLevels.DEBUG,
        env,
        `Got result ${result.value} from queryDialog: CREATE`
      );
      return result.value;
    }
    logMessage(LogLevels.DEBUG, env, 'Did not get queryDialog: CREATE');
    return;
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
}

async function rubinqueryrecenthistory(
  svcManager: ServiceManager.IManager,
  env: IEnvResponse
): Promise<RecentQueryResponse[]> {
  const count = 5;
  const endpoint = PageConfig.getBaseUrl() + `rubin/query/tap/history/${count}`;
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.INFO, env, `About to query TAP history at ${endpoint}`);
  const settings = svcManager.serverSettings;
  const retval: RecentQueryResponse[] = [];
  try {
    const res = await apiRequest(endpoint, init, settings);
    const qr_u = res as unknown;
    const qr_c = qr_u as IRecentQueryResponse[];
    logMessage(
      LogLevels.INFO,
      env,
      `Got query response ${JSON.stringify(qr_c, undefined, 2)}`
    );
    qr_c.forEach(qr => {
      retval.push(qr);
    });
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
  logMessage(
    LogLevels.INFO,
    env,
    `rubinqueryrecent history return: ${JSON.stringify(retval, undefined, 2)}`
  );
  return retval;
}

async function getRecentQueryMenu(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  rubinmenu: Menu
): Promise<Menu> {
  logMessage(LogLevels.INFO, env, 'Retrieving recent query menu');
  const { commands } = app;
  const retval: Menu = new Menu({ commands });
  try {
    const queries = await rubinqueryrecenthistory(svcManager, env);
    logMessage(
      LogLevels.INFO,
      env,
      `Recent queries: ${JSON.stringify(queries, undefined, 2)}`
    );
    queries.forEach(qr => {
      const submcmdId = `q-${qr.jobref}`;
      if (!commands.hasCommand(submcmdId)) {
        // If we haven't added this command before, do so now.
        commands.addCommand(submcmdId, {
          label: qr.jobref,
          execute: () => {
            openQueryFromJobref(
              app,
              docManager,
              svcManager,
              env,
              qr.jobref,
              rubinmenu
            );
          }
        });
      }
      const subm = new Menu({ commands });
      subm.addItem({
        command: submcmdId
      });
      subm.title.label = qr.text;
      retval.addItem({
        submenu: subm
      });
      logMessage(LogLevels.DEBUG, env, `Added ${qr.jobref}`);
    });
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      env,
      `Error performing recent query history ${error}`
    );
    throw new Error(`Failed to query recent history: ${error}`);
  }
  return retval;
}

async function rubinqueryallhistory(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse
): Promise<void> {
  const endpoint =
    PageConfig.getBaseUrl() + 'rubin/query/tap/notebooks/query_all';
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.INFO, env, 'Opening query-all notebook');
  const settings = svcManager.serverSettings;
  apiRequest(endpoint, init, settings).then(res => {
    const path_u = res as unknown;
    const path_c = path_u as IPathContainer;
    const path = path_c.path;
    docManager.open(path);
  });
}

async function rubintapquery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  rubinmenu: Menu
): Promise<void> {
  try {
    const jobref = await queryDialog(env);
    logMessage(LogLevels.INFO, env, `Query URL / ID is ${jobref}`);
    if (!jobref) {
      logMessage(LogLevels.WARNING, env, "Query URL was null'");
      return;
    }
    openQueryFromJobref(app, docManager, svcManager, env, jobref, rubinmenu);
  } catch (error) {
    logMessage(LogLevels.ERROR, env, `Error performing query ${error}`);
    throw new Error(`Failed to perform query: ${error}`);
  }
}

function openQueryFromJobref(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  jobref: string,
  rubinmenu: Menu
): void {
  logMessage(LogLevels.INFO, env, `Opening query for ${jobref}`);
  const body = JSON.stringify({
    type: 'tap',
    value: jobref
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
  // Opportunistic update of recent queries, since we just submitted a new
  // one...
  replaceRecentQueriesMenu(app, docManager, svcManager, env, rubinmenu);
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
