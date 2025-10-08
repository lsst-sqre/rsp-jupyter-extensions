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
import { format as formatSQL } from 'sql-formatter';

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

  // Store query data for tooltip functionality
  const queryDataMap = new Map<string, { sqlText: string; jobref: string }>();

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
          execute: async () => {
            await openQueryFromJobref(
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

      // Store query data for tooltip functionality
      queryDataMap.set(qr.jobref, { sqlText: qr.text, jobref: qr.jobref });

      // Create a direct menu item instead of a submenu
      retval.insertItem(menuindex, {
        type: 'command',
        command: submcmdId
      });

      logMessage(
        LogLevels.DEBUG,
        env,
        `Added ${submcmdId} to submenu for ${qr.jobref}`
      );
      menuindex += 10;
    });

    // Add single event delegation for all menu items
    addHoverTooltipsToMenu(retval, queryDataMap);
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

  try {
    const res = await apiRequest(endpoint, init, settings);
    const path_u = res as unknown;
    const path_c = path_u as IPathContainer;
    const path = path_c.path;
    docManager.open(path);
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      env,
      `Error opening query-all notebook: ${error}`
    );
    throw new Error(`Failed to open query-all notebook: ${error}`);
  }
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
    await openQueryFromJobref(
      app,
      docManager,
      svcManager,
      env,
      jobref,
      rubinmenu
    );
  } catch (error) {
    logMessage(LogLevels.ERROR, env, `Error performing query ${error}`);
    throw new Error(`Failed to perform query: ${error}`);
  }
}

async function openQueryFromJobref(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  jobref: string,
  rubinmenu: Menu
): Promise<void> {
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

  try {
    const res = await apiRequest(endpoint, init, settings);
    const r_u = res as unknown;
    const r_p = r_u as IPathContainer;
    const path = r_p.path;
    docManager.open(path);

    // Update menu in background (fire-and-forget) to avoid blocking UI
    replaceRubinMenuContents(app, docManager, svcManager, env, rubinmenu).catch(
      error => {
        logMessage(
          LogLevels.WARNING,
          env,
          `Background menu refresh failed: ${error}`
        );
        // Don't rethrow - this is a non-critical background operation
      }
    );
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      env,
      `Error opening query from jobref: ${error}`
    );
    throw new Error(`Failed to open query from jobref: ${error}`);
  }
}

/**
 * Add hover tooltip functionality to all menu items using event delegation
 */
function addHoverTooltipsToMenu(
  menu: Menu,
  queryDataMap: Map<string, { sqlText: string; jobref: string }>
): void {
  const menuNode = menu.node;
  if (!menuNode) {
    return;
  }

  // Track current hovered menu item to prevent rapid toggling
  let currentHoveredJobref: string | null = null;

  // Single event delegation for all menu items
  const handleMouseEnter = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (!target) {
      return;
    }

    // Find the closest menu item element
    const menuItem = target.closest('[data-command^="q-"]') as HTMLElement;

    if (!menuItem) {
      return;
    }

    const commandAttr = menuItem.getAttribute('data-command');

    if (!commandAttr || !commandAttr.startsWith('q-')) {
      return;
    }

    const jobref = commandAttr.substring(2); // Remove 'q-' prefix

    const queryData = queryDataMap.get(jobref);

    if (!queryData) {
      return;
    }

    // If we're already hovering over this item, don't show tooltip again
    if (currentHoveredJobref === jobref) {
      return;
    }

    // Clear any pending hide timeout when entering new item
    if (tooltipHideTimeout) {
      clearTimeout(tooltipHideTimeout);
      tooltipHideTimeout = null;
    }

    // Clear any pending show timeout from previous item
    if (tooltipShowTimeout) {
      clearTimeout(tooltipShowTimeout);
      tooltipShowTimeout = null;
    }

    // Update current hovered item
    currentHoveredJobref = jobref;

    // Add a small delay before showing tooltip to prevent rapid toggling
    tooltipShowTimeout = window.setTimeout(() => {
      showSQLTooltip(event, queryData.sqlText, queryData.jobref, () => {
        currentHoveredJobref = null;
      });
    }, 150); // Small delay to prevent flashy behavior
  };

  const handleMouseLeave = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (!target) {
      return;
    }

    const menuItem = target.closest('[data-command^="q-"]') as HTMLElement;

    if (!menuItem) {
      return;
    }

    const commandAttr = menuItem.getAttribute('data-command');

    if (!commandAttr || !commandAttr.startsWith('q-')) {
      return;
    }

    const jobref = commandAttr.substring(2);

    // Only process if we're leaving the item we're currently tracking
    if (currentHoveredJobref !== jobref) {
      return;
    }

    // DON'T clear the show timeout here - let it complete if user was hovering long enough
    // Only set the hide timeout

    // Clear any existing hide timeout before setting a new one
    if (tooltipHideTimeout) {
      clearTimeout(tooltipHideTimeout);
      tooltipHideTimeout = null;
    }

    // Add a longer delay before hiding to allow mouse to move to tooltip
    tooltipHideTimeout = window.setTimeout(() => {
      hideSQLTooltip();
      currentHoveredJobref = null;
    }, 300); // Longer delay to allow mouse movement to tooltip
  };

  const handleClick = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (!target) {
      return;
    }

    const menuItem = target.closest('[data-command^="q-"]') as HTMLElement;

    if (!menuItem) {
      return;
    }

    const commandAttr = menuItem.getAttribute('data-command');

    if (!commandAttr || !commandAttr.startsWith('q-')) {
      return;
    }

    hideSQLTooltip();
    currentHoveredJobref = null;
  };

  // Add event listeners with capture to ensure they're processed
  menuNode.addEventListener('mouseenter', handleMouseEnter, true);
  menuNode.addEventListener('mouseleave', handleMouseLeave, true);
  menuNode.addEventListener('click', handleClick, true);
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
 * Global tooltip show timeout
 */
let tooltipShowTimeout: number | null = null;

/**
 * Show SQL tooltip on hover with syntax highlighting
 */
function showSQLTooltip(
  event: MouseEvent,
  sqlText: string,
  jobref: string,
  resetHoveredJobref?: () => void
): void {
  // Remove existing tooltip only if one exists
  if (globalTooltip) {
    hideSQLTooltip();
  }

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
    min-width: 500px;
    max-width: 700px;
    min-height: 200px;
    max-height: 500px;
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
    max-height: 450px;
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

  // Format SQL first, then apply syntax highlighting
  const formattedSQL = formatSQLQuery(sqlText);
  sqlPre.innerHTML = highlightSQLBasic(formattedSQL);

  sqlContainer.appendChild(sqlPre);
  globalTooltip.appendChild(title);
  globalTooltip.appendChild(sqlContainer);
  document.body.appendChild(globalTooltip);

  // Position tooltip with better spacing for easier mouse access
  const rect = (event.target as HTMLElement).getBoundingClientRect();
  const tooltipRect = globalTooltip.getBoundingClientRect();

  // Position tooltip to the right of the menu item with some overlap for easier access
  let left = rect.right - 10; // Small overlap for easier mouse movement
  let top = rect.top - 5; // Slight vertical offset for better positioning

  // Adjust if tooltip would go off screen
  if (left + tooltipRect.width > window.innerWidth) {
    left = rect.left - tooltipRect.width + 10; // Position tooltip on the left with overlap
  }
  if (top + tooltipRect.height > window.innerHeight) {
    top = window.innerHeight - tooltipRect.height - 10;
  }
  if (top < 10) {
    top = 10; // Ensure tooltip doesn't go above viewport
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
    // Clear any existing hide timeout
    if (tooltipHideTimeout) {
      clearTimeout(tooltipHideTimeout);
    }
    // Add a small delay before hiding to prevent accidental hiding
    tooltipHideTimeout = window.setTimeout(() => {
      hideSQLTooltip();
      if (resetHoveredJobref) {
        resetHoveredJobref();
      }
    }, 100);
  });
}

/**
 * Hide SQL tooltip
 */
function hideSQLTooltip(): void {
  // Clear any pending timeouts
  if (tooltipHideTimeout) {
    clearTimeout(tooltipHideTimeout);
    tooltipHideTimeout = null;
  }
  if (tooltipShowTimeout) {
    clearTimeout(tooltipShowTimeout);
    tooltipShowTimeout = null;
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

  // Format SQL first, then apply syntax highlighting
  const formattedSQL = formatSQLQuery(sqlQuery);
  sqlEl.innerHTML = highlightSQLBasic(formattedSQL);
  card.appendChild(sqlEl);

  return card;
}

/**
 * Format SQL query with standard formatting rules
 */
function formatSQLQuery(sql: string): string {
  try {
    return formatSQL(sql, {
      language: 'sql',
      tabWidth: 2,
      keywordCase: 'upper',
      dataTypeCase: 'upper',
      functionCase: 'upper',
      identifierCase: 'preserve',
      indentStyle: 'standard',
      logicalOperatorNewline: 'before',
      expressionWidth: 50,
      linesBetweenQueries: 2
    });
  } catch (error) {
    // If formatting fails, return original SQL
    console.warn('SQL formatting failed:', error);
    return sql;
  }
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
