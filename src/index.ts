import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import { IMainMenu } from '@jupyterlab/mainmenu';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { INotebookTracker } from '@jupyterlab/notebook';

import { getServerConfig, INubladoConfigResponse } from './config';

import { activateRSPDisplayVersionExtension } from './displayversion';

import { activateRSPPDFExportExtension } from './pdfexport';

import { activateRSPQueryExtension } from './query';

import { activateRSPSavequitExtension } from './savequit';

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
  tracker: INotebookTracker
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
    logMessage(LogLevels.INFO, cfg, '...activating savequit extension...');
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
        abnormal,
        cfg
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

async function activateIndividualExtensions(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  statusBar: IStatusBar,
  tracker: INotebookTracker,
  abnormal: IAbnormalResponse,
  cfg: INubladoConfigResponse
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, '...activating savequit extension...');
  activateRSPSavequitExtension(app, mainMenu, docManager, cfg);
  logMessage(LogLevels.INFO, cfg, '...checking for abnormal startup...');
  if (abnormal.ABNORMAL_STARTUP) {
    // Give the user a warning dialog
    try {
      await abnormalDialog(abnormal, cfg);
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error showing abnormal dialog: ${error}`
      );
    }
  }
  logMessage(LogLevels.INFO, cfg, '...activating displayversion extension...');
  try {
    activateRSPDisplayVersionExtension(app, statusBar, cfg);
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
    activateRSPPDFExportExtension(app, mainMenu, docManager, cfg, tracker);
    logMessage(LogLevels.INFO, cfg, '...activated...');
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error activating pdfexport extension: ${error}`
    );
  }
  if (cfg.enable_rubin_query_menu) {
    logMessage(LogLevels.INFO, cfg, '...activating query extension...');
    try {
      await activateRSPQueryExtension(app, mainMenu, docManager, cfg);
      logMessage(LogLevels.INFO, cfg, '...activated...');
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error activating query extension: ${error}`
      );
    }
  } else {
    logMessage(
      LogLevels.INFO,
      cfg,
      '...skipping query extension (disabled in config)...'
    );
  }
  if (cfg.enable_tutorials_menu) {
    logMessage(LogLevels.INFO, cfg, '...activating tutorials extension...');
    try {
      activateRSPTutorialsExtension(app, mainMenu, docManager, cfg);
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
  logMessage(LogLevels.INFO, cfg, '...loaded rsp-jupyter-extensions.');
}

/**
 * Initialization data for the rspExtensions.
 */
const rspExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExtension,
  id: token.PLUGIN_ID,
  requires: [IMainMenu, IDocumentManager, IStatusBar, INotebookTracker],
  autoStart: true
};

export default rspExtension;
