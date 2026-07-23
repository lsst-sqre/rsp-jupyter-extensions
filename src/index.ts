import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import { IMainMenu } from '@jupyterlab/mainmenu';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { IFileBrowserFactory } from '@jupyterlab/filebrowser';

import { INotebookTracker } from '@jupyterlab/notebook';

import { ITranslator } from '@jupyterlab/translation';

import { activateRSPCollabExtension } from './collab';

import { getServerConfig, INubladoConfigResponse } from './config';

import { activateRSPStatusBarExtension } from './statusbar';

import { activateRSPPDFExportExtension } from './pdfexport';

import { activateRSPTAPQueriesExtension } from './tapqueries';

import { activateRSPQuitExtension } from './quit';

import { activateRSPTutorialsExtension } from './tutorials';

import { logMessage, LogLevels } from './logger';

import {
  getAbnormalStartup,
  IAbnormalResponse,
  abnormalDialog
} from './abnormal';

import * as token from './tokens';

function activateRSPExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  statusBar: IStatusBar,
  tracker: INotebookTracker,
  fileBrowserFactory: IFileBrowserFactory | null,
  translator: ITranslator | null
): void {
  logMessage(LogLevels.INFO, null, 'getting server configuration...');
  getServerConfig(app).then(async cfg => {
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `...cfg: ${JSON.stringify(cfg, undefined, 2)}...`
    );
    logMessage(LogLevels.INFO, cfg, '...got server configuration');
    logMessage(LogLevels.INFO, cfg, 'rsp-jupyter-extensions: loading...');
    logMessage(LogLevels.INFO, cfg, '...checking for abnormal startup...');
    const abnormal = await getAbnormalStartup(app);
    if (abnormal.ABNORMAL_STARTUP) {
      logMessage(
        LogLevels.WARNING,
        cfg,
        `...abnormal: ${JSON.stringify(abnormal, undefined, 2)}...`
      );
    } else {
      logMessage(LogLevels.DEBUG, cfg, '...no abnormal startup detected...');
    }
    logMessage(LogLevels.INFO, cfg, '...got abnormal startup info');
    try {
      await activateIndividualExtensions(
        app,
        mainMenu,
        docManager,
        statusBar,
        tracker,
        fileBrowserFactory,
        abnormal,
        cfg,
        translator
      );
    } catch (error) {
      logMessage(
        LogLevels.WARNING,
        cfg,
        `...activating extensions failed: ${error}...`
      );
    }
  });
}

/*
 * This single plugin (`rspExtension`) is the only one JupyterLab registers;
 * it declares all the shared tokens (IMainMenu, IDocumentManager, IStatusBar,
 * ...) in its `requires`/`optional`. The individual RSP extensions are then
 * activated manually below by calling their `activateRSP*Extension` functions
 * and passing those injected services along by hand. Each extension module
 * also default-exports a standalone JupyterFrontEndPlugin object, but those
 * are NOT registered on their own, so the `requires`/`optional` arrays on them
 * are not an active injection path -- this function is. Any service a
 * sub-extension needs must be added to `rspExtension` and threaded through
 * here.
 */
async function activateIndividualExtensions(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  statusBar: IStatusBar,
  tracker: INotebookTracker,
  fileBrowserFactory: IFileBrowserFactory | null,
  abnormal: IAbnormalResponse,
  cfg: INubladoConfigResponse,
  translator: ITranslator | null
): Promise<void> {
  /* Do this first so we have quit menu items even in abnormal startup. */
  logMessage(LogLevels.INFO, cfg, '...activating quit extension...');
  try {
    activateRSPQuitExtension(app, mainMenu, cfg, docManager, translator);
    logMessage(LogLevels.INFO, cfg, '...activated...');
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error activating quit extension: ${error}`
    );
  }
  logMessage(LogLevels.INFO, cfg, '...checking for abnormal startup...');
  if (abnormal.ABNORMAL_STARTUP) {
    // Give the user a warning dialog
    try {
      await abnormalDialog(abnormal, cfg, translator);
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error showing abnormal dialog: ${error}`
      );
    }
  }
  logMessage(LogLevels.INFO, cfg, '...activating statusbar extension...');
  try {
    activateRSPStatusBarExtension(app, statusBar, cfg);
    logMessage(LogLevels.INFO, cfg, '...activated...');
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error activating displayversion extension: ${error}`
    );
  }
  logMessage(LogLevels.INFO, cfg, '...activating pdfexport extension...');
  try {
    activateRSPPDFExportExtension(
      app,
      mainMenu,
      docManager,
      cfg,
      tracker,
      translator
    );
    logMessage(LogLevels.INFO, cfg, '...activated...');
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error activating pdfexport extension: ${error}`
    );
  }
  if (cfg.enable_jobs_menu) {
    logMessage(LogLevels.INFO, cfg, '...activating TAP queries extension...');
    try {
      await activateRSPTAPQueriesExtension(
        app,
        mainMenu,
        docManager,
        cfg,
        translator
      );
      logMessage(LogLevels.INFO, cfg, '...activated...');
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error activating TAP queries extension: ${error}`
      );
    }
  } else {
    logMessage(
      LogLevels.INFO,
      cfg,
      '...skipping TAP queries extension (disabled in config)...'
    );
  }
  if (cfg.enable_tutorials_menu) {
    logMessage(LogLevels.INFO, cfg, '...activating tutorials extension...');
    try {
      activateRSPTutorialsExtension(app, mainMenu, docManager, cfg, translator);
      logMessage(LogLevels.INFO, cfg, '...activated...');
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error activating tutorials extension: ${error}`
      );
    }
  } else {
    logMessage(
      LogLevels.INFO,
      cfg,
      '...skipping tutorials extension (disabled in config)...'
    );
  }
  if (cfg.collab_dir && fileBrowserFactory) {
    logMessage(LogLevels.INFO, cfg, '...activating collab extension...');
    try {
      await activateRSPCollabExtension(
        app,
        fileBrowserFactory,
        cfg,
        translator
      );
      logMessage(LogLevels.INFO, cfg, '...activated...');
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error activating collab extension: ${error}`
      );
    }
  } else {
    logMessage(
      LogLevels.INFO,
      cfg,
      '...skipping collab extension (no collab_dir in config)...'
    );
  }
  logMessage(LogLevels.INFO, cfg, '...loaded rsp-jupyter-extensions.');
}

/**
 * Initialization data for the rspExtensions.
 */
const rspExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExtension,
  id: token.PLUGIN_ID,
  description: 'Collection of JupyterLab extensions for the RSP',
  requires: [IMainMenu, IDocumentManager, IStatusBar, INotebookTracker],
  optional: [IFileBrowserFactory, ITranslator],
  autoStart: true
};

export default rspExtension;
