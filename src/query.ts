// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  Menu, Widget
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
  ServiceManager, ServerConnection
} from '@jupyterlab/services';

import {
  PageConfig
} from '@jupyterlab/coreutils';

/**
 * The command IDs used by the plugin.
 */
export
namespace CommandIDs {
  export const rubinQueryAPI: string = 'rubinqueryapi';
  export const rubinQuerySquash: string = 'rubinquerysquash';
};

/**
 * Interface used by the extension
 */
interface PathContainer {
  path: string;
}


/**
 * Activate the extension.
 */
function activateRubinQueryExtension(app: JupyterFrontEnd, mainMenu: IMainMenu, docManager: IDocumentManager): void {

  console.log('Rubin query extension: activated')

  let svcManager = app.serviceManager;

  app.commands.addCommand(CommandIDs.rubinQueryAPI, {
    label: 'Open from Query URL...',
    caption: 'Open notebook from supplied API query URL',
    execute: () => {
      rubinQuery(app, docManager, svcManager, "api")
    }
  });
  app.commands.addCommand(CommandIDs.rubinQuerySquash, {
    label: 'Open from CI ID...',
    caption: 'Open notebook from supplied Squash CI ID',
    execute: () => {
      rubinQuery(app, docManager, svcManager, "squash")
    }
  });

  // Add commands and menu itmes.
  const menu = new Menu({ commands: app.commands })
  menu.addItem({ command: CommandIDs.rubinQueryAPI })
  menu.addItem({ command: CommandIDs.rubinQuerySquash })
  menu.title.label = "Rubin"
  mainMenu.addMenu(menu, {
    rank: 420,
  });
}

class QueryHandler extends Widget {
  constructor(prompt: string) {
    super({ node: Private.createQueryNode(prompt) });
    this.addClass('lsst-rubin')
  }

  get inputNode(): HTMLInputElement {
    return this.node.getElementsByTagName('input')[0] as HTMLInputElement;
  }

  getValue(): string {
    return this.inputNode.value;
  }
}



function queryDialog(manager: IDocumentManager, prompt: string): Promise<string | null> {
  let options = {
    title: 'Query ID',
    body: new QueryHandler(prompt),
    focusNodeSelector: 'input',
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'CREATE' })]
  }
  return showDialog(options).then(result => {
    console.log("Result from queryDialog: ", result)
    if (!result.value) {
      console.log("No result.value from queryDialog");
      return null;
    }
    if (result.button.label === 'CREATE') {
      console.log("Got result ", result.value, " from queryDialog: CREATE")
      return Promise.resolve(result.value);
    }
    console.log("Did not get queryDialog: CREATE")
    return null;
  });
}

function apiRequest(url: string, init: RequestInit, settings: ServerConnection.ISettings): Promise<PathContainer> {
  /**
  * Make a request to our endpoint to get a pointer to a templated
  *  notebook for a given query
  *
  * @param url - the path for the query extension
  *
  * @param init - The POST + body for the extension
  *
  * @param settings - the settings for the current notebook server.
  *
  * @returns a Promise resolved with the JSON response
  */
  // Fake out URL check in makeRequest
  return ServerConnection.makeRequest(url, init, settings).then(
    response => {
      if (response.status !== 200) {
        return response.json().then(data => {
          throw new ServerConnection.ResponseError(response, data.message);
        });
      }
      return response.json();
    });
}

function rubinQuery(app: JupyterFrontEnd, docManager: IDocumentManager, svcManager: ServiceManager, qtype: string): void {
  let prompt = "Enter API Query URL"
  if (qtype == "squash") {
    prompt = "Enter Squash CI_ID"
  }

  queryDialog(docManager, prompt).then(queryid => {
    console.log("queryid is", queryid)
    if (!queryid) {
      console.log("queryid was null")
      return new Promise((res, rej) => { })
    }
    // Figure out some more generic way to get params
    let body = JSON.stringify({
      "query_id": queryid,
      "query_type": qtype
    })
    let endpoint = PageConfig.getBaseUrl() + "rubin/query"
    let init = {
      method: "POST",
      body: body
    }
    let settings = svcManager.serverSettings
    apiRequest(endpoint, init, settings).then(function(res) {
      let path = res.path
      docManager.open(path)
    });
    return new Promise((res, rej) => { })
  });
}


/**
 * Initialization data for the jupyterlab-lsstquery extension.
 */
const RubinQueryExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRubinQueryExtension,
  id: 'jupyter.extensions.jupyterlab-lsst-extension',
  requires: [
    IMainMenu,
    IDocumentManager
  ],
  autoStart: true,
};

export default RubinQueryExtension

namespace Private {
  /**
   * Create node for query handler.
   */

  export
    function createQueryNode(prompt: string): HTMLElement {
    let body = document.createElement('div');
    let qidLabel = document.createElement('label');
    qidLabel.textContent = prompt;
    let name = document.createElement('input');
    body.appendChild(qidLabel);
    body.appendChild(name);
    return body;
  }
}
