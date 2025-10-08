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
  env: IEnvResponse
): Promise<void> {
  logMessage(LogLevels.INFO, env, 'rsp-query...loading');

  const svcManager = app.serviceManager;
  const { commands } = app;
  const rubinmenu = new Menu({
    commands
  });
  mainMenu.addMenu(rubinmenu);
  rubinmenu.title.label = 'Rubin';

  await replaceRubinMenuContents(app, docManager, svcManager, env, rubinmenu);

  logMessage(LogLevels.INFO, env, 'rsp-query...loaded');
}

async function replaceRubinMenuContents(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  rubinmenu: Menu
): Promise<void> {
  const { commands } = app;

  if (!commands.hasCommand(CommandIDs.rubinqueryitem)) {
    commands.addCommand(CommandIDs.rubinqueryitem, {
      label: 'Open from your query history...',
      caption: 'Open notebook from supplied query jobref ID or URL',
      execute: () => {
        rubinTAPQuery(app, docManager, svcManager, env, rubinmenu);
      }
    });
  }
  if (!commands.hasCommand(CommandIDs.rubinquerynb)) {
    commands.addCommand(CommandIDs.rubinquerynb, {
      label: 'All queries',
      caption: 'Open notebook requesting all query history',
      execute: () => {
        rubinQueryAllHistory(app, docManager, svcManager, env);
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
          env,
          rubinmenu
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
  logMessage(LogLevels.DEBUG, env, 'inserted query dialog menu');
  rubinmenu.insertItem(20, { type: 'separator' });
  rubinmenu.insertItem(30, allquerynb);
  logMessage(LogLevels.DEBUG, env, 'inserted all-query notebook generator');
  rubinmenu.insertItem(40, { type: 'separator' });

  try {
    const recentquerymenu = await getRecentQueryMenu(
      app,
      docManager,
      svcManager,
      env,
      rubinmenu
    );
    logMessage(LogLevels.DEBUG, env, 'recent query menu retrieved');
    logMessage(LogLevels.DEBUG, env, 'inserting recent querymenu...');
    rubinmenu.insertItem(50, {
      type: 'submenu',
      submenu: recentquerymenu
    });
  } catch (error) {
    console.error(`Error getting recent query menu ${error}`);
    throw new Error(`Failed to get recent query menu: ${error}`);
  }
  logMessage(LogLevels.DEBUG, env, '...inserted recent query menu');
  rubinmenu.insertItem(60, { type: 'separator' });
  rubinmenu.insertItem(70, queryrefresh);
  logMessage(LogLevels.DEBUG, env, 'inserted query refresh');
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

async function rubinQueryRecentHistory(
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
      LogLevels.DEBUG,
      env,
      `Got query response ${JSON.stringify(qr_c, undefined, 2)}`
    );
    qr_c.forEach(qr => {
      const new_rqr: RecentQueryResponse = new RecentQueryResponse(qr);
      // Keep the original SQL text for tooltip display
      new_rqr.text = qr.text;
      logMessage(
        LogLevels.DEBUG,
        env,
        `query menu entry ${JSON.stringify(new_rqr, undefined, 2)}`
      );
      retval.push(new_rqr);
    });
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
  logMessage(
    LogLevels.DEBUG,
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
  retval.title.label = 'Recent Queries';
  try {
    const queries = await rubinQueryRecentHistory(svcManager, env);
    logMessage(
      LogLevels.DEBUG,
      env,
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
      } // Not gonna worry about pruning no-longer-displayed commands.
      // Create a direct menu item instead of a submenu
      retval.insertItem(menuindex, {
        type: 'command',
        command: submcmdId
      });

      // Add hover tooltip functionality to the main menu item
      addHoverTooltipToMainMenu(retval, qr.text, qr.jobref, menuindex);

      logMessage(
        LogLevels.DEBUG,
        env,
        `Added ${submcmdId} to submenu for ${qr.jobref}`
      );
      menuindex += 10;
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

async function rubinQueryAllHistory(
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

async function rubinTAPQuery(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  rubinmenu: Menu
): Promise<void> {
  try {
    const jobref = await queryDialog(env);
    logMessage(LogLevels.DEBUG, env, `Query URL / ID is ${jobref}`);
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
  // Opportunistic update of menu, since we just submitted a new query.
  replaceRubinMenuContents(app, docManager, svcManager, env, rubinmenu);
}

/**
 * Add hover tooltip functionality to a main menu item
 */
function addHoverTooltipToMainMenu(
  menu: Menu,
  sqlText: string,
  jobref: string,
  menuIndex: number
): void {
  // Use event delegation on the menu node instead of setTimeout
  const menuNode = menu.node;
  if (menuNode) {
    // Add event delegation for hover events
    menuNode.addEventListener('mouseenter', event => {
      const target = event.target as HTMLElement;
      if (target && target.getAttribute('data-command') === `q-${jobref}`) {
        // Clear any pending hide timeout
        if (tooltipHideTimeout) {
          clearTimeout(tooltipHideTimeout);
          tooltipHideTimeout = null;
        }
        showSQLTooltip(event, sqlText, jobref);
      }
    });

    menuNode.addEventListener('mouseleave', event => {
      const target = event.target as HTMLElement;
      if (target && target.getAttribute('data-command') === `q-${jobref}`) {
        // Add a small delay before hiding to allow mouse to move to tooltip
        tooltipHideTimeout = window.setTimeout(() => {
          hideSQLTooltip();
        }, 100);
      }
    });

    menuNode.addEventListener('click', event => {
      const target = event.target as HTMLElement;
      if (target && target.getAttribute('data-command') === `q-${jobref}`) {
        hideSQLTooltip();
      }
    });
  }
}

/**
 * Global tooltip element
 */
let globalTooltip: HTMLElement | null = null;

/**
 * Global tooltip hide timeout
 */
let tooltipHideTimeout: number | null = null;

/**
 * Show SQL tooltip on hover with syntax highlighting
 */
function showSQLTooltip(
  event: MouseEvent,
  sqlText: string,
  jobref: string
): void {
  // Remove existing tooltip
  hideSQLTooltip();

  // Create tooltip element
  globalTooltip = document.createElement('div');
  globalTooltip.className = 'sql-hover-tooltip';
  globalTooltip.style.cssText = `
    position: fixed;
    z-index: 10000;
    background: #ffffff;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    padding: 16px;
    max-width: 500px;
    max-height: 300px;
    overflow: hidden;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 12px;
    line-height: 1.4;
    cursor: text;
    user-select: text;
  `;

  // Create title
  const title = document.createElement('div');
  title.textContent = `Query: ${jobref}`;
  title.style.cssText = `
    font-weight: 600;
    color: #24292e;
    margin-bottom: 8px;
    font-size: 13px;
  `;

  // Create container for SQL display
  const sqlContainer = document.createElement('div');
  sqlContainer.style.cssText = `
    margin: 0;
    background: #f6f8fa;
    border: 1px solid #e1e4e8;
    border-radius: 4px;
    overflow: auto;
    max-height: 250px;
  `;

  // Create pre element for SQL with syntax highlighting
  const sqlPre = document.createElement('pre');
  sqlPre.style.cssText = `
    margin: 0;
    padding: 12px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: #24292e;
  `;

  // Apply syntax highlighting using the existing highlightSQLBasic function
  sqlPre.innerHTML = highlightSQLBasic(sqlText);

  sqlContainer.appendChild(sqlPre);
  globalTooltip.appendChild(title);
  globalTooltip.appendChild(sqlContainer);
  document.body.appendChild(globalTooltip);

  // Position tooltip closer to the menu item for easier mouse access
  const rect = (event.target as HTMLElement).getBoundingClientRect();
  const tooltipRect = globalTooltip.getBoundingClientRect();

  let left = rect.right - 2; // Position tooltip slightly overlapping for easier access
  let top = rect.top;

  // Adjust if tooltip would go off screen
  if (left + tooltipRect.width > window.innerWidth) {
    left = rect.left - tooltipRect.width + 2; // Position tooltip slightly overlapping on the left
  }
  if (top + tooltipRect.height > window.innerHeight) {
    top = window.innerHeight - tooltipRect.height - 10;
  }

  globalTooltip.style.left = `${left}px`;
  globalTooltip.style.top = `${top}px`;

  // Add hover listeners to keep tooltip visible when mouse enters it
  globalTooltip.addEventListener('mouseenter', () => {
    // Clear any pending hide timeout when mouse enters tooltip
    if (tooltipHideTimeout) {
      clearTimeout(tooltipHideTimeout);
      tooltipHideTimeout = null;
    }
  });

  globalTooltip.addEventListener('mouseleave', () => {
    // Hide tooltip when mouse leaves
    hideSQLTooltip();
  });
}

/**
 * Hide SQL tooltip
 */
function hideSQLTooltip(): void {
  // Clear any pending hide timeout
  if (tooltipHideTimeout) {
    clearTimeout(tooltipHideTimeout);
    tooltipHideTimeout = null;
  }

  if (globalTooltip) {
    globalTooltip.remove();
    globalTooltip = null;
  }
}

/**
 * Create a beautiful SQL query card for display
 */
export function createSQLCard(sqlQuery: string, title?: string): HTMLElement {
  const card = document.createElement('div');
  card.className = 'sql-card';
  card.style.cssText = `
    background: #ffffff;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 13px;
    line-height: 1.5;
  `;

  if (title) {
    const titleEl = document.createElement('div');
    titleEl.className = 'sql-card-title';
    titleEl.style.cssText = `
      font-weight: 600;
      color: #24292e;
      margin-bottom: 8px;
      font-size: 14px;
    `;
    titleEl.textContent = title;
    card.appendChild(titleEl);
  }

  const sqlEl = document.createElement('pre');
  sqlEl.className = 'sql-card-content';
  sqlEl.style.cssText = `
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: #24292e;
    background: #f6f8fa;
    padding: 12px;
    border-radius: 4px;
    border: 1px solid #e1e4e8;
  `;

  // Apply syntax highlighting
  sqlEl.innerHTML = highlightSQLBasic(sqlQuery);
  card.appendChild(sqlEl);

  return card;
}

/**
 * Basic SQL syntax highlighting function
 */
function highlightSQLBasic(sql: string): string {
  // SQL keywords to highlight
  const keywords = [
    'SELECT',
    'FROM',
    'WHERE',
    'ORDER',
    'BY',
    'GROUP',
    'HAVING',
    'JOIN',
    'INNER',
    'LEFT',
    'RIGHT',
    'OUTER',
    'ON',
    'AS',
    'AND',
    'OR',
    'NOT',
    'IN',
    'EXISTS',
    'BETWEEN',
    'LIKE',
    'IS',
    'NULL',
    'DISTINCT',
    'LIMIT',
    'INSERT',
    'UPDATE',
    'DELETE',
    'CREATE',
    'DROP',
    'ALTER',
    'TABLE',
    'INDEX',
    'VIEW',
    'PROCEDURE',
    'FUNCTION',
    'TRIGGER',
    'DATABASE',
    'SCHEMA',
    'UNION',
    'ALL',
    'CASE',
    'WHEN',
    'THEN',
    'ELSE',
    'END',
    'IF',
    'WHILE',
    'FOR',
    'LOOP',
    'BEGIN',
    'COMMIT',
    'ROLLBACK',
    'TRANSACTION',
    'GRANT',
    'REVOKE',
    'PRIMARY',
    'KEY',
    'FOREIGN',
    'REFERENCES',
    'CONSTRAINT',
    'CHECK',
    'DEFAULT',
    'AUTO_INCREMENT',
    'VARCHAR',
    'INT',
    'BIGINT',
    'SMALLINT',
    'TINYINT',
    'DECIMAL',
    'FLOAT',
    'DOUBLE',
    'CHAR',
    'TEXT',
    'DATE',
    'TIME',
    'DATETIME',
    'TIMESTAMP',
    'BOOLEAN',
    'BLOB',
    'JSON'
  ];

  // Escape HTML entities first to prevent double-escaping
  let highlighted = sql
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  // Highlight keywords
  keywords.forEach(keyword => {
    const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
    highlighted = highlighted.replace(
      regex,
      `<span style="color: #cf222e; font-weight: bold;">${keyword.toUpperCase()}</span>`
    );
  });

  // Highlight strings (single and double quotes)
  highlighted = highlighted.replace(
    /(&#39;)((?:\\.|(?!\1)[^\\])*?)\1/g,
    '<span style="color: #0a3069;">$1$2$1</span>'
  );
  highlighted = highlighted.replace(
    /(&quot;)((?:\\.|(?!\1)[^\\])*?)\1/g,
    '<span style="color: #0a3069;">$1$2$1</span>'
  );

  // Highlight numbers
  highlighted = highlighted.replace(
    /\b\d+(\.\d+)?\b/g,
    '<span style="color: #0a3069; font-weight: bold;">$&</span>'
  );

  // Highlight comments (-- and /* */)
  highlighted = highlighted.replace(
    /--.*$/gm,
    '<span style="color: #6a737d; font-style: italic;">$&</span>'
  );
  highlighted = highlighted.replace(
    /\/\*[\s\S]*?\*\//g,
    '<span style="color: #6a737d; font-style: italic;">$&</span>'
  );

  return highlighted;
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
