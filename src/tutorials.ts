// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { showDialog, Dialog } from '@jupyterlab/apputils';

import { PageConfig } from '@jupyterlab/coreutils';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { ServerConnection } from '@jupyterlab/services';

import { Menu } from '@lumino/widgets';

//import { ServiceManager, ServerConnection } from '@jupyterlab/services';
import { IMainMenu } from '@jupyterlab/mainmenu';

import * as token from './tokens';

enum Actions {
  COPY = 'copy',
  FETCH = 'fetch'
}

enum Dispositions {
  PROMPT = 'prompt',
  OVERWRITE = 'overwrite',
  ABORT = 'abort'
}

interface ITutorialsEntryResponse {
  menu_name: string;
  action: Actions;
  disposition: Dispositions;
  parent: string;
  src: string;
  dest: string;
}

class TutorialsEntry implements ITutorialsEntryResponse {
  menu_name: string;
  action: Actions;
  disposition: Dispositions;
  parent: string;
  src: string;
  dest: string;

  constructor(inp: ITutorialsEntryResponse) {
    (this.menu_name = inp.menu_name),
      (this.action = inp.action),
      (this.disposition = inp.disposition),
      (this.parent = inp.parent),
      (this.src = inp.src),
      (this.dest = inp.dest);
  }
}

interface ITutorialsHierarchyResponse {
  entries: { [name: string]: ITutorialsEntryResponse } | null;
  subhierarchies: { [name: string]: ITutorialsHierarchyResponse } | null;
}

class TutorialsHierarchy implements ITutorialsHierarchyResponse {
  entries: { [name: string]: TutorialsEntry } | null = null;
  subhierarchies: { [name: string]: TutorialsHierarchy } | null = null;

  constructor(inp: ITutorialsHierarchyResponse, name: string | null = null) {
    if (name === null) {
      name = '<unnamed>';
    }
    console.log(`Building hierarchy ${name}`);
    if (inp.entries !== null) {
      for (const entry in inp.entries) {
        console.log(`${name} -> entry ${entry}`);
        const e_obj = inp.entries[entry];
        if (e_obj === null) {
          console.log(`skipping null entry ${entry}`);
          continue;
        }
        if (this.entries === null) {
          this.entries = {};
        }
        console.log(
          `adding entry ${entry}: ${JSON.stringify(e_obj, undefined, 2)}`
        );
        this.entries[entry] = new TutorialsEntry(e_obj);
      }
    }
    if (inp.subhierarchies !== null) {
      const sublist = Object.keys(inp.subhierarchies);
      console.log(`Subhierarchies: ${sublist}`);
      for (const subh of sublist) {
        if (inp.subhierarchies === null) {
          console.log(`Somehow, subhierarchies is null at ${name}`);
          continue;
        }
        console.log(`${name} -> subhierarchy ${subh}`);
        const s_obj = inp.subhierarchies[subh];
        if (s_obj === null) {
          console.log(`skipping null subhierarchy ${subh}`);
          continue;
        }
        if (this.subhierarchies === null) {
          this.subhierarchies = {};
        }
        console.log(`recurse: new subhierarchy of ${name} ${subh}`);
        this.subhierarchies[subh] = new TutorialsHierarchy(s_obj, subh);
      }
    }
    console.log(`hierarchy ${name} built`);
  }
}

function apiGetTutorialsHierarchy(
  settings: ServerConnection.ISettings
): Promise<TutorialsHierarchy> {
  /**
   * Make a request to our endpoint to get the tutorial hierarchy
   *
   * @param settings - the settings for the current notebook server
   *
   * @returns a Promise resolved with the JSON response
   */
  // Fake out URL check in makeRequest
  return ServerConnection.makeRequest(
    PageConfig.getBaseUrl() + 'rubin/tutorials',
    { method: 'GET' },
    settings
  ).then(response => {
    if (response.status !== 200) {
      return response.json().then(data => {
        throw new ServerConnection.ResponseError(response, data.message);
      });
    }
    return response.json().then(data => {
      console.log(`Response: ${JSON.stringify(data, undefined, 2)}`);
      const h_i = data as ITutorialsHierarchyResponse;
      const tut = new TutorialsHierarchy(h_i);
      console.log('Created TutorialsHierary from response');
      console.log('==============================');
      return tut;
    });
  });
}

function apiPostTutorialsEntry(
  settings: ServerConnection.ISettings,
  docManager: IDocumentManager,
  entry: TutorialsEntry
): void {
  /**
   * Make a request to our endpoint to copy a file into place and open it
   *
   * @param settings - the settings for the current notebook server
   *
   * @param entry - the entry corresponding to the file to work with
   *
   * @returns a Promise resolved with the JSON response
   */
  // Fake out URL check in makeRequest
  console.log(
    `Sending POST to tutorials endpoint with data ${JSON.stringify(
      entry,
      undefined,
      2
    )}`
  );
  ServerConnection.makeRequest(
    PageConfig.getBaseUrl() + 'rubin/tutorials',
    { method: 'POST', body: JSON.stringify(entry) },
    settings
  ).then(response => {
    if (response.status === 409) {
      // File exists; prompt user
      overwriteDialog(entry.dest, docManager).then(verb => {
        console.log(`Dialog result was ${verb}`);
        if (verb !== 'OVERWRITE') {
          // Don't do the thing!
          return;
        }
        const newEntryModel = {
          menu_name: entry.menu_name,
          action: entry.action,
          disposition: Dispositions.OVERWRITE,
          parent: entry.parent,
          src: entry.src,
          dest: entry.dest
        } as ITutorialsEntryResponse;
        const newEntry = new TutorialsEntry(newEntryModel);
        // Resubmit response with request to overwrite file.
        apiPostTutorialsEntry(settings, docManager, newEntry);
        return;
      });
    }
    if (response.status === 307 || response.status === 200) {
      // File got copied.
      console.log(`Opening file ${entry.dest}`);
      docManager.openOrReveal(entry.dest);
    } else {
      console.log(`Unexpected response status ${response.status}`);
    }
    return;
  });
}

function overwriteDialog(
  dest: string,
  manager: IDocumentManager
): Promise<any> {
  const options = {
    title: 'Target file exists',
    body: `Overwrite file '${dest}' ?`,
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'OVERWRITE' })]
  };
  console.log('Showing overwrite dialog');
  return showDialog(options).then(result => {
    if (!result) {
      console.log('No result from queryDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    console.log('Result from overwriteDialog: ', result);
    if (!result.button) {
      console.log('No result.button from overwriteDialog');
      return new Promise((res, rej) => {
        /* Nothing */
      });
    }
    if (result.button.label === 'OVERWRITE') {
      console.log(
        'Got result ',
        result.button.label,
        ' from overwriteDialog: OVERWRITE'
      );
      return Promise.resolve(result.button.label);
    }
    console.log('Did not get overwriteDialog: OVERWRITE');
    return new Promise((res, rej) => {
      /* Nothing */
    });
  });
}

export function activateRSPTutorialsExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager
): void {
  console.log('rsp-tutorials: loading...');
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  function buildTutorialsMenu(
    name: string,
    hierarchy: ITutorialsHierarchyResponse,
    parentmenu: Menu | null
  ): void {
    console.log(`building tutorials menu for ${name}`);
    if (parentmenu === null) {
      // Set up submenu
      const { commands } = app;
      const tutorialsmenu = new Menu({ commands });
      tutorialsmenu.title.label = 'Tutorials';
      parentmenu = tutorialsmenu;
      console.log('set up top level Tutorials menu');
      mainMenu.addMenu(tutorialsmenu);
    } else {
      console.log(`supplied parent menu=${parentmenu.title.label}`);
    }
    const parent = parentmenu.title.label;
    console.log(`building tutorials menu ${name}, parent=${parent}`);

    if (hierarchy.subhierarchies !== null) {
      // Recursively add submenus
      for (const subh in hierarchy.subhierarchies) {
        const s_obj = hierarchy.subhierarchies[subh];
        // Skip null or empty entries
        if (s_obj === null) {
          console.log(`skipping empty hierarchy ${subh}`);
          continue;
        }
        if (s_obj.entries === null && s_obj.subhierarchies === null) {
          console.log(
            `Skipping hierarchy ${subh} with no entries or subhierarchies`
          );
          continue;
        }
        console.log(`adding submenu ${subh} to ${parent}`);
        const { commands } = app;
        const smenu = new Menu({ commands });
        smenu.title.label = subh;
        parentmenu.addItem({ submenu: smenu, type: 'submenu' });
        console.log(`recurse: hierarchy ${subh}`);
        // Now recurse down new menu/subhierarchy
        buildTutorialsMenu(subh, s_obj, smenu);
        console.log(`recursion done; emerged from ${subh}`);
      }
    }
    console.log(`done with subhierarchies for ${name}`);

    if (hierarchy.entries !== null) {
      parentmenu.addItem({ type: 'separator' });
      for (const entry in hierarchy.entries) {
        const { commands } = app;
        const entry_obj = hierarchy.entries[entry];
        const cmdId = `${entry_obj.parent}/${entry_obj.menu_name}`;
        console.log(
          `creating command ${cmdId} for entry ${JSON.stringify(
            entry,
            undefined,
            2
          )}`
        );
        commands.addCommand(cmdId, {
          label: entry,
          execute: () => {
            apiPostTutorialsEntry(settings, docManager, entry_obj);
          }
        });
        console.log(`adding item ${cmdId} to ${parent}`);
        parentmenu.addItem({
          command: cmdId,
          type: 'command'
        });
      }
    }
    console.log(`done with entries for ${name} ; ${parentmenu.title.label}`);

    console.log(`done with ${name}`);
  }

  apiGetTutorialsHierarchy(settings).then(res => {
    if (res) {
      const o_res = res as TutorialsHierarchy;
      buildTutorialsMenu('root', o_res, null);
    }
  });

  console.log('rsp-tutorials: ...loaded.');
}

/**
 * Initialization data for the jupyterlab-lsstquery extension.
 */
const rspTutorialsExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPTutorialsExtension,
  id: token.TUTORIALS_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspTutorialsExtension;
