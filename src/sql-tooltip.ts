// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import { Menu } from '@lumino/widgets';
import { format as formatSQL } from 'sql-formatter';

/**
 * A widget class that provides SQL hover tooltip functionality for menu items
 */
export class SQLHoverTooltip {
  private globalTooltip: HTMLElement | null = null;
  private tooltipHideTimeout: number | null = null;
  private tooltipShowTimeout: number | null = null;
  private currentHoveredJobref: string | null = null;
  private queryDataMap: Map<string, { sqlText: string; jobref: string }>;

  constructor(queryDataMap: Map<string, { sqlText: string; jobref: string }>) {
    this.queryDataMap = queryDataMap;
  }

  /**
   * Add hover tooltip functionality to all menu items using event delegation
   */
  attachToMenu(menu: Menu): void {
    const menuNode = menu.node;
    if (!menuNode) {
      return;
    }

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

      const queryData = this.queryDataMap.get(jobref);

      if (!queryData) {
        return;
      }

      // If we're already hovering over this item, don't show tooltip again
      if (this.currentHoveredJobref === jobref) {
        return;
      }

      // Clear any pending hide timeout when entering new item
      if (this.tooltipHideTimeout) {
        clearTimeout(this.tooltipHideTimeout);
        this.tooltipHideTimeout = null;
      }

      // Clear any pending show timeout from previous item
      if (this.tooltipShowTimeout) {
        clearTimeout(this.tooltipShowTimeout);
        this.tooltipShowTimeout = null;
      }

      // Update current hovered item
      this.currentHoveredJobref = jobref;

      // Add a small delay before showing tooltip to prevent rapid toggling
      this.tooltipShowTimeout = window.setTimeout(() => {
        this.showTooltip(event, queryData.sqlText, queryData.jobref);
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
      if (this.currentHoveredJobref !== jobref) {
        return;
      }

      // DON'T clear the show timeout here - let it complete if user was hovering long enough
      // Only set the hide timeout

      // Clear any existing hide timeout before setting a new one
      if (this.tooltipHideTimeout) {
        clearTimeout(this.tooltipHideTimeout);
        this.tooltipHideTimeout = null;
      }

      // Add a longer delay before hiding to allow mouse to move to tooltip
      this.tooltipHideTimeout = window.setTimeout(() => {
        this.hideTooltip();
        this.currentHoveredJobref = null;
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

      this.hideTooltip();
      this.currentHoveredJobref = null;
    };

    // Add event listeners with capture to ensure they're processed
    menuNode.addEventListener('mouseenter', handleMouseEnter, true);
    menuNode.addEventListener('mouseleave', handleMouseLeave, true);
    menuNode.addEventListener('click', handleClick, true);
  }

  /**
   * Show SQL tooltip on hover with syntax highlighting
   */
  private showTooltip(
    event: MouseEvent,
    sqlText: string,
    jobref: string
  ): void {
    // Remove existing tooltip only if one exists
    if (this.globalTooltip) {
      this.hideTooltip();
    }

    // Create tooltip element
    this.globalTooltip = document.createElement('div');
    this.globalTooltip.className = 'sql-hover-tooltip';
    this.globalTooltip.style.cssText = `
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
    const formattedSQL = this.formatSQLQuery(sqlText);
    sqlPre.innerHTML = this.highlightSQLBasic(formattedSQL);

    sqlContainer.appendChild(sqlPre);
    this.globalTooltip.appendChild(title);
    this.globalTooltip.appendChild(sqlContainer);
    document.body.appendChild(this.globalTooltip);

    // Position tooltip with better spacing for easier mouse access
    const rect = (event.target as HTMLElement).getBoundingClientRect();
    const tooltipRect = this.globalTooltip.getBoundingClientRect();

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

    this.globalTooltip.style.left = `${left}px`;
    this.globalTooltip.style.top = `${top}px`;

    // Add hover listeners to keep tooltip visible when mouse enters it
    this.globalTooltip.addEventListener('mouseenter', () => {
      // Clear any pending hide timeout when mouse enters tooltip
      if (this.tooltipHideTimeout) {
        clearTimeout(this.tooltipHideTimeout);
        this.tooltipHideTimeout = null;
      }
    });

    this.globalTooltip.addEventListener('mouseleave', () => {
      // Clear any existing hide timeout
      if (this.tooltipHideTimeout) {
        clearTimeout(this.tooltipHideTimeout);
      }
      // Add a small delay before hiding to prevent accidental hiding
      this.tooltipHideTimeout = window.setTimeout(() => {
        this.hideTooltip();
        this.currentHoveredJobref = null;
      }, 100);
    });
  }

  /**
   * Hide SQL tooltip
   */
  private hideTooltip(): void {
    // Clear any pending timeouts
    if (this.tooltipHideTimeout) {
      clearTimeout(this.tooltipHideTimeout);
      this.tooltipHideTimeout = null;
    }
    if (this.tooltipShowTimeout) {
      clearTimeout(this.tooltipShowTimeout);
      this.tooltipShowTimeout = null;
    }

    if (this.globalTooltip) {
      this.globalTooltip.remove();
      this.globalTooltip = null;
    }
  }

  /**
   * Create a beautiful SQL query card for display
   */
  static createSQLCard(sqlQuery: string, title?: string): HTMLElement {
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
    const formattedSQL = SQLHoverTooltip.formatSQLQueryStatic(sqlQuery);
    sqlEl.innerHTML = SQLHoverTooltip.highlightSQLBasicStatic(formattedSQL);
    card.appendChild(sqlEl);

    return card;
  }

  /**
   * Format SQL query with standard formatting rules
   */
  private formatSQLQuery(sql: string): string {
    return SQLHoverTooltip.formatSQLQueryStatic(sql);
  }

  /**
   * Static version of formatSQLQuery for use in createSQLCard
   */
  static formatSQLQueryStatic(sql: string): string {
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
  private highlightSQLBasic(sql: string): string {
    return SQLHoverTooltip.highlightSQLBasicStatic(sql);
  }

  /**
   * Static version of highlightSQLBasic for use in createSQLCard
   */
  static highlightSQLBasicStatic(sql: string): string {
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
}
