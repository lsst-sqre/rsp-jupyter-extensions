import { Menu } from '@lumino/widgets';

import { showDialog, Dialog } from '@jupyterlab/apputils';

import { IMainMenu } from '@jupyterlab/mainmenu';

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { INotebookTracker } from '@jupyterlab/notebook';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { ServiceManager } from '@jupyterlab/services';

import { PageConfig } from '@jupyterlab/coreutils';

import { LogLevels, logMessage } from './logger';

import * as token from './tokens';
import { IEnvResponse } from './environment';
import { apiRequest } from './request';

/**
 * The command IDs used by the plugin.
 */
export namespace CommandIDs {
  export const pdfExport = 'pdfexport:pdfexport';
}

interface IPDFExportResponse {
  path: string | null;
  error: string | null;
}

/**
 * Activate the jupyterlab extension.
 */
export function activateRSPPDFExportExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  env: IEnvResponse,
  tracker: INotebookTracker
): void {
  logMessage(LogLevels.INFO, null, 'rsp-pdfexport: loading...');

  const svcManager = app.serviceManager;

  const { commands } = app;

  commands.addCommand(CommandIDs.pdfExport, {
    label: 'Export current notebook to PDF (typst)',
    caption: 'Export current notebook to PDF with typst',
    execute: () => {
      pdfExport(app, docManager, svcManager, env, tracker);
    }
  });

  // Find the export menu.  If we can't, use the File menu itself.
  const exportTo = mainMenu.fileMenu.items.find(
    item =>
      item.type === 'submenu' &&
      item.submenu?.id === 'jp-mainmenu-file-notebookexport'
  )?.submenu;

  if (exportTo) {
    exportTo.addItem({
      command: CommandIDs.pdfExport,
      args: {
        format: 'PDF-typst',
        label: 'PDF-typst',
        isPalette: false
      }
    });
  } else {
    const menu: Menu.IItemOptions[] = [{ command: CommandIDs.pdfExport }];
    // Put it near the bottom of File menu
    const rank = 140;
    mainMenu.fileMenu.addGroup(menu, rank);
  }

  logMessage(LogLevels.INFO, env, 'rsp-pdfexport: ...loaded.');
}

async function pdfExport(
  app: JupyterFrontEnd,
  docManager: IDocumentManager,
  svcManager: ServiceManager.IManager,
  env: IEnvResponse,
  tracker: INotebookTracker
): Promise<void> {
  // Find current notebook
  if (!tracker) {
    logMessage(LogLevels.WARNING, env, 'Tracker is undefined');
    return;
  }
  const current = tracker.currentWidget;
  if (!current) {
    // Nothing to work with
    logMessage(LogLevels.DEBUG, env, 'No current notebook');
    return;
  }
  const { context } = current;
  if (context.model.dirty && !context.model.readOnly) {
    // Save before render.
    await context.save();
  }
  const path = current.context.path; // Now we have the path to the notebook.

  const endpoint = PageConfig.getBaseUrl() + 'rubin/pdfexport';
  const body = JSON.stringify({
    path: path
  });
  const init = {
    method: 'POST',
    body: body
  };
  const settings = svcManager.serverSettings;

  try {
    const res = await apiRequest(endpoint, init, settings);
    const r_u = res as unknown;
    const r_p = r_u as IPDFExportResponse;
    const path = r_p.path;
    const error = r_p.error;
    logMessage(
      LogLevels.DEBUG,
      env,
      `Got query response ${JSON.stringify(r_p, undefined, 2)}`
    );
    if (path) {
      docManager.open(path);
    } else {
      if (!error) {
        // This shouldn't happen; the backend checks that one of path or
        // error is present.
        await PDFError('unknown error', env);
      } else {
        await PDFError(error, env);
      }
    }
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      env,
      `Error converting ${path} to PDF: ${error}`
    );
    throw new Error(`Failed to convert ${path} to PDF: ${error}`);
  }
}

export async function PDFError(err: string, env: IEnvResponse): Promise<void> {
  const options = {
    title: 'PDF Conversion Error',
    body: err,
    focusNodeSelector: 'input',
    buttons: [Dialog.warnButton({ label: 'OK' })]
  };
  try {
    const result = await showDialog(options);
    if (!result) {
      logMessage(LogLevels.DEBUG, env, 'No result from PDFErrorDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, env, `Result from PDFErrorDialog: ${result}`);
    if (!result.value) {
      logMessage(LogLevels.DEBUG, env, 'No result.value from PDFErrorDialog');
      return;
    }
    if (!result.button) {
      logMessage(LogLevels.DEBUG, env, 'No result.button from PDFErrorDialog');
      return;
    }
    return;
  } catch (error) {
    console.error(`Error showing abnormal PDF error dialog ${error}`);
    throw new Error(`Failed to show PDF error dialog: ${error}`);
  }
}

/**
 * Initialization data for the PDF export extension.
 */
const rspPDFExportExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPPDFExportExtension,
  id: token.PDFEXPORT_ID,
  requires: [IMainMenu, IDocumentManager, INotebookTracker],
  autoStart: false
};

export default rspPDFExportExtension;
