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
import { apiRequest } from './request';
import { SQLHoverTooltip } from './sql-tooltip';
import { INubladoConfigResponse } from './config';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const rubinqueryitem = 'rubinqueryitem';
  export const rubinhistory = 'rubinhistory';
  export const rubinquerynb = 'rubinquerynb';
  export const rubinqueryrefresh = 'rubinqueryrefresh';
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

/**
 * Activate the extension.
 */
export async function activateRSPQueryExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, 'rsp-query...loading');

  const svcManager = app.serviceManager;
  const { commands } = app;
  const rubinmenu = new Menu({
    commands
  });
  mainMenu.addMenu(rubinmenu);
  rubinmenu.title.label = 'Rubin';

  try {
    await replaceRubinMenuContents(app, docManager, svcManager, rubinmenu, cfg);
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      'Failed to replace Rubin menu contents: {error}'
    );
  }

  logMessage(LogLevels.INFO, cfg, 'rsp-query...loaded');
}

async function replaceRubinMenuContents(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  rubinmenu: Menu,
  cfg: INubladoConfigResponse
): Promise<void> {
  const { commands } = app;

  if (!commands.hasCommand(CommandIDs.rubinqueryitem)) {
    commands.addCommand(CommandIDs.rubinqueryitem, {
      label: 'Open from your query history...',
      caption:
        'Open notebook from supplied query jobref ID, dataset:id, or URL',
      execute: () => {
        rubinTAPQuery(app, docManager, svcManager, rubinmenu, cfg);
      }
    });
  }
  if (!commands.hasCommand(CommandIDs.rubinquerynb)) {
    commands.addCommand(CommandIDs.rubinquerynb, {
      label: 'All queries',
      caption: 'Open notebook requesting all query history',
      execute: () => {
        rubinQueryAllHistory(app, docManager, svcManager, cfg);
      }
    });
  }
  if (!commands.hasCommand(CommandIDs.rubinqueryrefresh)) {
    commands.addCommand(CommandIDs.rubinqueryrefresh, {
      label: 'Refresh query history',
      caption: 'Refresh query history',
      execute: async () => {
        await replaceRubinMenuContents(
          app,
          docManager,
          svcManager,
          rubinmenu,
          cfg
        );
      }
    });
  }

  // Get rid of menu contents
  rubinmenu.clearItems();

  // Add commands and menu itmes.
  const querymenu: Menu.IItemOptions = { command: CommandIDs.rubinqueryitem };
  const allquerynb: Menu.IItemOptions = { command: CommandIDs.rubinquerynb };
  const queryrefresh: Menu.IItemOptions = {
    command: CommandIDs.rubinqueryrefresh
  };

  rubinmenu.insertItem(10, querymenu);
  logMessage(LogLevels.DEBUG, cfg, 'inserted query dialog menu');
  rubinmenu.insertItem(20, { type: 'separator' });
  rubinmenu.insertItem(30, allquerynb);
  logMessage(LogLevels.DEBUG, cfg, 'inserted all-query notebook generator');
  rubinmenu.insertItem(40, { type: 'separator' });

  try {
    const recentquerymenu = await getRecentQueryMenu(
      app,
      docManager,
      svcManager,
      rubinmenu,
      cfg
    );
    logMessage(LogLevels.DEBUG, cfg, 'recent query menu retrieved');
    logMessage(LogLevels.DEBUG, cfg, 'inserting recent querymenu...');
    rubinmenu.insertItem(50, {
      type: 'submenu',
      submenu: recentquerymenu
    });
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error getting recent query menu ${error}`
    );
    throw new Error(`Failed to get recent query menu: ${error}`);
  }
  logMessage(LogLevels.DEBUG, cfg, '...inserted recent query menu');
  rubinmenu.insertItem(60, { type: 'separator' });
  rubinmenu.insertItem(70, queryrefresh);
  logMessage(LogLevels.DEBUG, cfg, 'inserted query refresh');
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

async function queryDialog(
  cfg: INubladoConfigResponse
): Promise<string | void> {
  const options = {
    title: 'Query Jobref ID or URL',
    body: new QueryHandler(),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, cfg, 'No result from queryDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, cfg, `Result from queryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.value from queryDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.button from queryDialog');
      return;
    }
    if (result.button.label === 'CREATE') {
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `Got result ${result.value} from queryDialog: CREATE`
      );
      return result.value;
    }
    logMessage(LogLevels.DEBUG, cfg, 'Did not get queryDialog: CREATE');
    return;
  } catch (error) {
    logMessage(LogLevels.ERROR, cfg, `Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
}

async function rubinQueryRecentHistory(
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse
): Promise<RecentQueryResponse[]> {
  const count = 5;
  const endpoint = PageConfig.getBaseUrl() + `rubin/query/tap/history/${count}`;
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.INFO, cfg, `About to query TAP history at ${endpoint}`);
  const settings = svcManager.serverSettings;
  const retval: RecentQueryResponse[] = [];
  try {
    const res = await apiRequest(endpoint, init, settings);
    const qr_u = res as unknown;
    const qr_c = qr_u as IRecentQueryResponse[];
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Got query response ${JSON.stringify(qr_c, undefined, 2)}`
    );
    qr_c.forEach(qr => {
      const new_rqr: RecentQueryResponse = new RecentQueryResponse(qr);
      // Keep the original SQL text for tooltip display
      new_rqr.text = qr.text;
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `query menu entry ${JSON.stringify(new_rqr, undefined, 2)}`
      );
      retval.push(new_rqr);
    });
  } catch (error) {
    logMessage(LogLevels.ERROR, cfg, `Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
  logMessage(
    LogLevels.DEBUG,
    cfg,
    `rubinqueryrecent history return: ${JSON.stringify(retval, undefined, 2)}`
  );
  return retval;
}

async function getRecentQueryMenu(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  rubinmenu: Menu,
  cfg: INubladoConfigResponse
): Promise<Menu> {
  logMessage(LogLevels.INFO, cfg, 'Retrieving recent query menu');
  const { commands } = app;
  const retval: Menu = new Menu({ commands });
  retval.title.label = 'Recent Queries';

  // Store query data for tooltip functionality
  const queryDataMap = new Map<string, { sqlText: string; jobref: string }>();

  try {
    const queries = await rubinQueryRecentHistory(svcManager, cfg);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Recent queries: ${JSON.stringify(queries, undefined, 2)}`
    );
    let menuindex = 10;
    queries.forEach(qr => {
      const submcmdId = `q-${qr.jobref}`;
      if (!commands.hasCommand(submcmdId)) {
        // If we haven't added this command before, do so now.
        commands.addCommand(submcmdId, {
          label: qr.jobref, // Show just the jobref as the label
          caption: qr.text, // Use the full SQL as the caption/tooltip
          execute: async () => {
            await openQueryFromJobref(
              app,
              docManager,
              svcManager,
              qr.jobref,
              rubinmenu,
              cfg
            );
          }
        });
      } // Not gonna worry about pruning no-longer-displayed commands.

      // Store query data for tooltip functionality
      queryDataMap.set(qr.jobref, { sqlText: qr.text, jobref: qr.jobref });

      // Create a direct menu item instead of a submenu
      retval.insertItem(menuindex, {
        type: 'command',
        command: submcmdId
      });

      logMessage(
        LogLevels.DEBUG,
        cfg,
        `Added ${submcmdId} to submenu for ${qr.jobref}`
      );
      menuindex += 10;
    });

    // Add single event delegation for all menu items
    const sqlTooltip = new SQLHoverTooltip(queryDataMap);
    sqlTooltip.attachToMenu(retval);
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error performing recent query history ${error}`
    );
    throw new Error(`Failed to query recent history: ${error}`);
  }
  return retval;
}

async function rubinQueryAllHistory(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse
): Promise<void> {
  const endpoint =
    PageConfig.getBaseUrl() + 'rubin/query/tap/notebooks/query_all';
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.INFO, cfg, 'Opening query-all notebook');
  const settings = svcManager.serverSettings;

  try {
    const res = await apiRequest(endpoint, init, settings);
    const path_u = res as unknown;
    const path_c = path_u as IPathContainer;
    const path = path_c.path;
    docManager.open(path);
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error opening query-all notebook: ${error}`
    );
    throw new Error(`Failed to open query-all notebook: ${error}`);
  }
}

async function rubinTAPQuery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  rubinmenu: Menu,
  cfg: INubladoConfigResponse
): Promise<void> {
  try {
    const jobref = await queryDialog(cfg);
    logMessage(LogLevels.DEBUG, cfg, `Query URL / ID is ${jobref}`);
    if (!jobref) {
      logMessage(LogLevels.WARNING, cfg, "Query URL was null'");
      return;
    }
    await openQueryFromJobref(
      app,
      docManager,
      svcManager,
      jobref,
      rubinmenu,
      cfg
    );
  } catch (error) {
    logMessage(LogLevels.ERROR, cfg, `Error performing query ${error}`);
    throw new Error(`Failed to perform query: ${error}`);
  }
}

async function openQueryFromJobref(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  jobref: string,
  rubinmenu: Menu,
  cfg: INubladoConfigResponse
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, `Opening query for ${jobref}`);
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

  try {
    const res = await apiRequest(endpoint, init, settings);
    const r_u = res as unknown;
    const r_p = r_u as IPathContainer;
    const path = r_p.path;
    docManager.open(path);

    // Update menu in background (fire-and-forget) to avoid blocking UI
    replaceRubinMenuContents(app, docManager, svcManager, rubinmenu, cfg).catch(
      error => {
        logMessage(
          LogLevels.WARNING,
          cfg,
          `Background menu refresh failed: ${error}`
        );
        // Don't rethrow - this is a non-critical background operation
      }
    );
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error opening query from jobref: ${error}`
    );
    throw new Error(`Failed to open query from jobref: ${error}`);
  }
}

/**
 * Create a beautiful SQL query card for display
 * @deprecated Use SQLHoverTooltip.createSQLCard instead
 */
export function createSQLCard(sqlQuery: string, title?: string): HTMLElement {
  return SQLHoverTooltip.createSQLCard(sqlQuery, title);
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
