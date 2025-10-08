import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { IStatusBar } from '@jupyterlab/statusbar';

import { IMainMenu } from '@jupyterlab/mainmenu';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { getServerEnvironment } from './environment';

import { activateRSPDisplayVersionExtension } from './displayversion';

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
  statusBar: IStatusBar
): void {
  logMessage(LogLevels.INFO, null, 'getting server environment...');
  getServerEnvironment(app).then(async env => {
    logMessage(
      LogLevels.DEBUG,
      env,
      `...env: ${JSON.stringify(env, undefined, 2)}...`
    );
    logMessage(LogLevels.INFO, env, '...got server environment');
    logMessage(LogLevels.INFO, env, 'rsp-lab-extension: loading...');
    logMessage(LogLevels.INFO, env, '...activating savequit extension...');
    activateRSPSavequitExtension(app, mainMenu, docManager, env);
    logMessage(LogLevels.INFO, env, '...checking for abnormal startup...');
    if (env.ABNORMAL_STARTUP === 'TRUE') {
      // Give the user a warning dialog
      try {
        await abnormalDialog(env);
      } catch (error) {
        logMessage(
          LogLevels.ERROR,
          env,
          `Error showing abnormal dialog: ${error}`
        );
      }
    }
    logMessage(
      LogLevels.INFO,
      env,
      '...activating displayversion extension...'
    );
    activateRSPDisplayVersionExtension(app, statusBar, env);
    logMessage(LogLevels.INFO, env, '...activated...');
    logMessage(LogLevels.INFO, env, '...activating query extension...');
    if (env.RSP_SITE_TYPE === 'science' || env.RSP_SITE_TYPE === 'staff') {
      try {
        await activateRSPQueryExtension(app, mainMenu, docManager, env);
        logMessage(LogLevels.INFO, env, '...activated...');
      } catch (error) {
        logMessage(
          LogLevels.ERROR,
          env,
          `Error activating query extension: ${error}`
        );
      }
    } else {
      logMessage(
        LogLevels.INFO,
        env,
        `...skipping query extension because site type is '${env.RSP_SITE_TYPE}'...`
      );
    }
    logMessage(LogLevels.INFO, env, '...activated...');
    logMessage(LogLevels.INFO, env, '...activating tutorials extension...');
    if (env.RSP_SITE_TYPE === 'science') {
      activateRSPTutorialsExtension(app, mainMenu, docManager, env);
      logMessage(LogLevels.INFO, env, '...activated...');
    } else {
      logMessage(
        LogLevels.INFO,
        env,
        `...skipping tutorials extension because site type is '${env.RSP_SITE_TYPE}'...`
      );
    }
    logMessage(LogLevels.INFO, env, '...loaded rsp-lab-extension.');
  });
}

/**
 * Initialization data for the rspExtensions.
 */
const rspExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExtension,
  id: token.PLUGIN_ID,
  requires: [IMainMenu, IDocumentManager, IStatusBar],
  autoStart: true
};

export default rspExtension;
