import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  IStatusBar
} from '@jupyterlab/statusbar';

import {
  IMainMenu
} from '@jupyterlab/mainmenu';

import {
  IDocumentManager
} from '@jupyterlab/docmanager';

import {
  activateRSPDisplayVersionExtension,
} from "./displayversion"

import {
  activateRSPQueryExtension,
} from "./query"

import {
  activateRSPSavequitExtension,
} from "./savequit"

import * as token from "./tokens";


function activateRSPExtension(app: JupyterFrontEnd, mainMenu: IMainMenu, docManager: IDocumentManager, statusBar: IStatusBar): void {
  console.log('rsp-lab-extension: loading...');
  console.log('...activating displayversion extension...');
  activateRSPDisplayVersionExtension(app, statusBar);
  console.log('...activated...')
  console.log('...activating query extension...');
  activateRSPQueryExtension(app, mainMenu, docManager);
  console.log('...activated...')
  console.log('...activating savequit extension...');
  activateRSPSavequitExtension(app, mainMenu, docManager);
  console.log('...activated...')
  console.log('...loaded rsp-lab-extension.')
}

/**
 * Initialization data for the rspExtensions.
 */
const rspExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPExtension,
  id: token.PLUGIN_ID,
  requires: [
    IMainMenu,
    IDocumentManager,
    IStatusBar
  ],
  autoStart: true,
};

export default rspExtension
