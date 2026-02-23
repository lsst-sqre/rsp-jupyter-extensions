import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import { IMainMenu } from '@jupyterlab/mainmenu';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { INotebookTracker } from '@jupyterlab/notebook';

import { getServerConfig, INubladoConfigResponse } from './config';

import { queryRepertoire, IRepertoireResponse } from './discovery';

import { getServerEnvironment, IEnvResponse } from './environment';

import { activateRSPDisplayVersionExtension } from './displayversion';

import { activateRSPPDFExportExtension } from './pdfexport';

import { activateRSPQueryExtension } from './query';

import { activateRSPSavequitExtension } from './savequit';

import { activateRSPTutorialsExtension } from './tutorials';

import { logMessage, LogLevels } from './logger';

import { abnormalDialog } from './abnormal';

import * as token from './tokens';

function activateRSPExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  statusBar: IStatusBar,
  tracker: INotebookTracker
): void {
  logMessage(LogLevels.INFO, null, 'rsp-jupyter-extensions: loading...');
  logMessage(LogLevels.INFO, null, '...getting server config...');
  getServerConfig(app).then(async cfg => {
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `...cfg: ${JSON.stringify(cfg, undefined, 2)}...`
    );
    logMessage(LogLevels.INFO, cfg, '...got server config');
    logMessage(LogLevels.INFO, cfg, '...getting server environment...');
    const env = await getServerEnvironment(app);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `...env: ${JSON.stringify(env, undefined, 2)}...`
    );
    logMessage(LogLevels.INFO, cfg, '...got server environment');
    logMessage(LogLevels.INFO, cfg, '...getting service discovery...');
    const dsc = await queryRepertoire(cfg);
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `...dsc: ${JSON.stringify(dsc, undefined, 2)}...`
    );
    logMessage(LogLevels.INFO, cfg, '...got service discovery...');
    try {
      await activateIndividualExtensions(
        app,
        mainMenu,
        docManager,
        statusBar,
        tracker,
        env,
        cfg,
        dsc
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
  env: IEnvResponse,
  cfg: INubladoConfigResponse,
  dsc: IRepertoireResponse
): Promise<void> {
  logMessage(LogLevels.INFO, cfg, '...activating savequit extension...');
  activateRSPSavequitExtension(app, mainMenu, docManager, dsc, cfg);
  logMessage(LogLevels.INFO, cfg, '...checking for abnormal startup...');
  if (env.ABNORMAL_STARTUP === 'TRUE') {
    // Give the user a warning dialog
    try {
      await abnormalDialog(env, cfg);
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
    activateRSPDisplayVersionExtension(app, statusBar, cfg, dsc);
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
    activateRSPPDFExportExtension(app, mainMenu, docManager, tracker, cfg);
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
