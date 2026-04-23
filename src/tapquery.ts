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
import { INubladoConfigResponse } from './config';
import { apiRequest } from './request';
import { SQLHoverTooltip } from './sql-tooltip';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const tapqueryitem = 'tapqueryitem';
  export const taphistory = 'taphistory';
  export const tapquerynb = 'tapquerynb';
  export const tapqueryrefresh = 'tapqueryrefresh';
}

/**
 * Interface used by the extension
 */
interface IPathContainer {
  path: string;
}

interface IRecentTAPQueryResponse {
  jobref: string;
  text: string;
}

class RecentTAPQueryResponse implements IRecentTAPQueryResponse {
  jobref: string;
  text: string;

  constructor(inp: IRecentTAPQueryResponse) {
    (this.jobref = inp.jobref), (this.text = inp.text);
  }
}

interface ITAPQueryHistoryResponse {
  [dataset: string]: IRecentTAPQueryResponse[];
}

class TAPQueryHistoryResponse implements ITAPQueryHistoryResponse {
  [dataset: string]: RecentTAPQueryResponse[];

  constructor(inp: ITAPQueryHistoryResponse) {
    for (const dsname in inp) {
      if (inp[dsname] !== null && inp[dsname].length !== 0) {
        const responses: IRecentTAPQueryResponse[] = [];
        for (const resp of inp[dsname]) {
          responses.push(new RecentTAPQueryResponse(resp));
        }
        this[dsname] = responses;
      }
    }
  }
}
/**
 * Activate the extension.
 */
export async function activateRSPTAPQueryExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, 'rsp-tapquery...loading');

  const svcManager = app.serviceManager;
  const { commands } = app;
  const jobsmenu = new Menu({
    commands
  });
  mainMenu.addMenu(jobsmenu);
  jobsmenu.title.label = 'Jobs';

  await replaceJobsmenuContents(app, docManager, svcManager, cfg, jobsmenu);

  logMessage(LogLevels.INFO, cfg, 'rsp-tapquery...loaded');
}

async function replaceJobsmenuContents(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse,
  jobsmenu: Menu
): Promise<void> {
  const { commands } = app;

  if (!commands.hasCommand(CommandIDs.tapqueryitem)) {
    commands.addCommand(CommandIDs.tapqueryitem, {
      label: 'Open from your TAP query history...',
      caption:
        'Open notebook from supplied query jobref ID, dataset:id, or URL',
      execute: () => {
        tapQuery(app, docManager, svcManager, cfg, jobsmenu);
      }
    });
  }
  if (!commands.hasCommand(CommandIDs.tapquerynb)) {
    commands.addCommand(CommandIDs.tapquerynb, {
      label: 'All TAP queries',
      caption: 'Open notebook requesting all TAP query history',
      execute: () => {
        tapQueryAllHistory(docManager, svcManager, cfg);
      }
    });
  }
  if (!commands.hasCommand(CommandIDs.tapqueryrefresh)) {
    commands.addCommand(CommandIDs.tapqueryrefresh, {
      label: 'Refresh TAP query history',
      caption: 'Refresh TAP query history',
      execute: async () => {
        await replaceJobsmenuContents(
          app,
          docManager,
          svcManager,
          cfg,
          jobsmenu
        );
      }
    });
  }

  // Get rid of menu contents
  jobsmenu.clearItems();

  // Add commands and menu itmes.
  const tapquerymenu: Menu.IItemOptions = { command: CommandIDs.tapqueryitem };
  const alltapquerynb: Menu.IItemOptions = { command: CommandIDs.tapquerynb };
  const tapqueryrefresh: Menu.IItemOptions = {
    command: CommandIDs.tapqueryrefresh
  };

  jobsmenu.insertItem(10, tapquerymenu);
  logMessage(LogLevels.DEBUG, cfg, 'inserted TAP query dialog menu');
  jobsmenu.insertItem(20, { type: 'separator' });
  jobsmenu.insertItem(30, alltapquerynb);
  logMessage(LogLevels.DEBUG, cfg, 'inserted all-TAP-query notebook generator');
  jobsmenu.insertItem(40, { type: 'separator' });

  try {
    const recenttapquerymenu = await getRecentTAPQueryMenu(
      app,
      docManager,
      svcManager,
      cfg,
      jobsmenu
    );
    logMessage(LogLevels.DEBUG, cfg, 'recent TAP query menu retrieved');
    logMessage(LogLevels.DEBUG, cfg, 'inserting recent TAQ query menu...');
    jobsmenu.insertItem(50, {
      type: 'submenu',
      submenu: recenttapquerymenu
    });
  } catch (error) {
    console.error(`Error getting recent TAP query menu ${error}`);
    throw new Error(`Failed to get recent TAP query menu: ${error}`);
  }
  logMessage(LogLevels.DEBUG, cfg, '...inserted recent TAP query menu');
  jobsmenu.insertItem(60, { type: 'separator' });
  jobsmenu.insertItem(70, tapqueryrefresh);
  logMessage(LogLevels.DEBUG, cfg, 'inserted TAP query refresh');
}

class TAPQueryHandler extends Widget {
  constructor() {
    super({ node: Private.createTAPQueryNode() });
    this.addClass('tap-qh');
  }

  get inputNode(): HTMLInputElement {
    return this.node.getElementsByTagName('input')[0] as HTMLInputElement;
  }

  getValue(): string {
    return this.inputNode.value;
  }
}

async function tapQueryDialog(
  cfg: INubladoConfigResponse
): Promise<string | void> {
  const options = {
    title: 'TAP Query Jobref ID or URL',
    body: new TAPQueryHandler(),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, cfg, 'No result from tapQueryDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, cfg, `Result from tapQueryDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.value from tapQueryDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.button from tapQueryDialog');
      return;
    }
    if (result.button.label === 'CREATE') {
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `Got result ${result.value} from tapQueryDialog: CREATE`
      );
      return result.value;
    }
    logMessage(LogLevels.DEBUG, cfg, 'Did not get tapQueryDialog: CREATE');
    return;
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
}

async function tapQueryRecentHistory(
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse
): Promise<TAPQueryHistoryResponse> {
  const count = 5;
  const endpoint =
    PageConfig.getBaseUrl() + `rubin/queries/tap/history/${count}`;
  const init = {
    method: 'GET'
  };
  logMessage(LogLevels.INFO, cfg, `About to query TAP history at ${endpoint}`);
  const settings = svcManager.serverSettings;
  let retval = new TAPQueryHistoryResponse({});
  try {
    const res = await apiRequest(endpoint, init, settings);
    const qh_c = res as unknown as ITAPQueryHistoryResponse;
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Got query history response: ${JSON.stringify(qh_c, undefined, 2)}`
    );
    retval = new TAPQueryHistoryResponse(qh_c);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `tapqueryRecentHistory: ${JSON.stringify(retval, undefined, 2)}`
    );
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
  return retval;
}

async function getRecentTAPQueryMenu(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse,
  jobsmenu: Menu
): Promise<Menu> {
  logMessage(LogLevels.INFO, cfg, 'Retrieving recent TAP query menu');
  const { commands } = app;
  const retval: Menu = new Menu({ commands });
  retval.title.label = 'Recent Queries';

  try {
    const qhist = await tapQueryRecentHistory(svcManager, cfg);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `Query history: ${JSON.stringify(qhist, undefined, 2)}`
    );
    for (const dataset in qhist) {
      let menuindex = 10;
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `TAP query entries for dataset ${dataset}`
      );
      const qval = qhist[dataset];
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `Query history entry: ${JSON.stringify(qval, undefined, 2)}`
      );
      if (!qval || qval.length === 0) {
        continue;
      }
      // Store query data for tooltip functionality
      const tapQueryDataMap = new Map<
        string,
        { sqlText: string; jobref: string }
      >();
      const submMenu = new Menu({ commands });
      submMenu.title.label = dataset;
      retval.addItem({ submenu: submMenu, type: 'submenu' });
      for (const tqr of qval) {
        const submcmdId = `tq-${tqr.jobref}`;
        if (!commands.hasCommand(submcmdId)) {
          // If we haven't added this command before, do so now.
          // Remove the part before the colon, if there is a colon.  If
          // not, use the whole string (indexOf returns -1 if the search
          // character isn't present).
          const jr = tqr.jobref.substring(1 + tqr.jobref.indexOf(':'));
          commands.addCommand(submcmdId, {
            label: jr, // Show just the jobref as the label
            caption: tqr.text, // Use the full SQL as the caption/tooltip
            execute: async () => {
              await openTAPQueryFromJobref(
                app,
                docManager,
                svcManager,
                cfg,
                tqr.jobref,
                jobsmenu
              );
            }
          });
        }
        // Not gonna worry about pruning no-longer-displayed commands.

        // Store query data for tooltip functionality
        tapQueryDataMap.set(tqr.jobref, {
          sqlText: tqr.text,
          jobref: tqr.jobref
        });

        // Create a direct menu item instead of a submenu
        submMenu.insertItem(menuindex, {
          type: 'command',
          command: submcmdId
        });

        logMessage(
          LogLevels.DEBUG,
          cfg,
          `Added ${submcmdId} to submenu ${dataset} for ${tqr.jobref}`
        );
        menuindex += 10;
      }
      // Add single event delegation for all menu items
      const sqlTooltip = new SQLHoverTooltip(tapQueryDataMap);
      sqlTooltip.attachToMenu(submMenu);
    }
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error performing recent TAP query history ${error}`
    );
    throw new Error(`Failed to acquire recent TAP query history: ${error}`);
  }
  return retval;
}

async function tapQueryAllHistory(
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse
): Promise<void> {
  const endpoint =
    PageConfig.getBaseUrl() + 'rubin/queries/tap/notebooks/query_all';
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

async function tapQuery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse,
  jobsmenu: Menu
): Promise<void> {
  try {
    const jobref = await tapQueryDialog(cfg);
    logMessage(LogLevels.DEBUG, cfg, `TAP Query URL / ID is ${jobref}`);
    if (!jobref) {
      logMessage(LogLevels.WARNING, cfg, "TAP Query URL was null'");
      return;
    }
    await openTAPQueryFromJobref(
      app,
      docManager,
      svcManager,
      cfg,
      jobref,
      jobsmenu
    );
  } catch (error) {
    logMessage(LogLevels.ERROR, cfg, `Error performing TAP query ${error}`);
    throw new Error(`Failed to perform TAP query: ${error}`);
  }
}

async function openTAPQueryFromJobref(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  cfg: INubladoConfigResponse,
  jobref: string,
  jobsmenu: Menu
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, `Opening TAP query for ${jobref}`);
  const body = JSON.stringify({
    type: 'tap',
    value: jobref
  });
  const endpoint = PageConfig.getBaseUrl() + 'rubin/queries';
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
    replaceJobsmenuContents(app, docManager, svcManager, cfg, jobsmenu).catch(
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
      `Error opening TAP query from jobref: ${error}`
    );
    throw new Error(`Failed to open TAP query from jobref: ${error}`);
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
 * Initialization data for the query extension.
 */
const rspTAPQueryExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPTAPQueryExtension,
  id: token.TAPQUERY_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspTAPQueryExtension;

namespace Private {
  /**
   * Create node for query handler.
   */

  export function createTAPQueryNode(): HTMLElement {
    const body = document.createElement('div');
    const qidLabel = document.createElement('label');
    qidLabel.textContent = 'Enter TAP Query Jobref ID or URL';
    const name = document.createElement('input');
    body.appendChild(qidLabel);
    body.appendChild(name);
    return body;
  }
}
