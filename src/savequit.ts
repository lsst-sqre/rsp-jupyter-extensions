// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  Menu
} from '@lumino/widgets';

import {
  showDialog, Dialog
} from '@jupyterlab/apputils';

import {
  IMainMenu
} from '@jupyterlab/mainmenu';

import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  IDocumentManager
} from '@jupyterlab/docmanager';

import {
  PageConfig
} from '@jupyterlab/coreutils';

import {
  ServiceManager, ServerConnection
} from '@jupyterlab/services';

import {
  each
} from '@lumino/algorithm';

import * as token from "./tokens";

/**
 * The command IDs used by the plugin.
 */
export
namespace CommandIDs {
  export const saveQuit: string = 'savequit:savequit';
  export const justQuit: string = 'justquit:justquit';
};


/**
 * Activate the jupyterhub extension.
 */
export function activateRSPSavequitExtension(app: JupyterFrontEnd, mainMenu: IMainMenu, docManager: IDocumentManager): void {

  console.log('rsp-savequit: loading...');

  let svcManager = app.serviceManager;

  const { commands } = app;

  commands.addCommand(CommandIDs.saveQuit, {
    label: 'Save All and Exit',
    caption: 'Save open notebooks and destroy container',
    execute: () => {
      saveAndQuit(app, docManager, svcManager)
    }
  });

  commands.addCommand(CommandIDs.justQuit, {
    label: 'Exit Without Saving',
    caption: 'Destroy container',
    execute: () => {
      justQuit(app, docManager, svcManager)
    }
  });

  // Add commands and menu itmes.
  let menu: Menu.IItemOptions[] =
    [
      { command: CommandIDs.saveQuit },
      { command: CommandIDs.justQuit },
    ]
  // Put it at the bottom of file menu
  let rank = 150;
  mainMenu.fileMenu.addGroup(menu, rank);

  console.log('rsp-savequit: ...loaded.');
}

function hubDeleteRequest(app: JupyterFrontEnd): Promise<Response> {
  let svcManager = app.serviceManager;
  let settings = svcManager.serverSettings
  let endpoint = PageConfig.getBaseUrl() + "rubin/hub"
  let init = {
    method: "DELETE",
  }
  console.log("hubRequest: URL: ", endpoint, " | Settings:", settings)
  return ServerConnection.makeRequest(endpoint, init, settings)
}

function saveAll(app: JupyterFrontEnd, docManager: IDocumentManager, svcManager: ServiceManager): Promise<any> {
  let promises: Promise<any>[] = [];
  each(app.shell.widgets('main'), widget => {
    if (widget) {
      let context = docManager.contextForWidget(widget);
      if (context) {
        console.log("Saving context for widget:", { id: widget.id })
        promises.push(context.save())
      } else {
        console.log("No context for widget:", { id: widget.id })
      }
    }
  })
  console.log("Waiting for all save-document promises to resolve.")
  let r = Promise.resolve(1)
  if (promises) {
    Promise.all(promises);
    r = promises[0]
  }
  return r
}


function saveAndQuit(app: JupyterFrontEnd, docManager: IDocumentManager, svcManager: ServiceManager): Promise<any> {
  infoDialog()
  const retval = Promise.resolve(saveAll(app, docManager, svcManager));
  retval.then((res) => {
    return justQuit(app, docManager, svcManager)
  });
  retval.catch((err) => {
    console.log("saveAll failed: ", err.message);
  });
  console.log("Save and Quit complete.")
  return retval
}

function justQuit(app: JupyterFrontEnd, docManager: IDocumentManager, svcManager: ServiceManager): Promise<any> {
  infoDialog()
  let targetEndpoint = "/"
  return Promise.resolve(hubDeleteRequest(app)
    .then(() => {
      console.log("Quit complete.")
    })
    .then(() => {
      window.location.replace(targetEndpoint)
    }))
}

function infoDialog(): Promise<void> {
  let options = {
    title: "Redirecting to landing page",
    body: "JupyterLab cleaning up and redirecting to landing page.",
    buttons: [Dialog.okButton({ label: 'Got it!' })]
  };
  return showDialog(options).then(() => {
    console.log("Info dialog panel displayed")
  })
}

/**
 * Initialization data for the rspSavequit extension.
 */
const rspSavequitExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPSavequitExtension,
  id: token.SAVEQUIT_ID,
  requires: [
    IMainMenu,
    IDocumentManager
  ],
  autoStart: false,
};

export default rspSavequitExtension;

