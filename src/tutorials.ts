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
import { INubladoConfigResponse } from './config';
import { LogLevels, logMessage } from './logger';
import { apiRequest } from './request';

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
  cfg: INubladoConfigResponse | null = null;

  constructor(
    inp: ITutorialsHierarchyResponse,
    name: string | null = null,
    cfg: INubladoConfigResponse | null = null
  ) {
    if (name === null) {
      name = '<unnamed>';
    }
    this.cfg = cfg;
    logMessage(LogLevels.INFO, this.cfg, `Building hierarchy ${name}`);
    if (inp.entries !== null) {
      for (const entry in inp.entries) {
        logMessage(LogLevels.DEBUG, this.cfg, `${name} -> entry ${entry}`);
        const e_obj = inp.entries[entry];
        if (e_obj === null) {
          logMessage(LogLevels.DEBUG, this.cfg, `skipping null entry ${entry}`);
          continue;
        }
        if (this.entries === null) {
          this.entries = {};
        }
        logMessage(
          LogLevels.DEBUG,
          this.cfg,
          `adding entry ${entry}: ${JSON.stringify(e_obj, undefined, 2)}`
        );
        this.entries[entry] = new TutorialsEntry(e_obj);
      }
    }
    if (inp.subhierarchies !== null) {
      const sublist = Object.keys(inp.subhierarchies);
      logMessage(LogLevels.DEBUG, this.cfg, `Subhierarchies: ${sublist}`);
      for (const subh of sublist) {
        if (inp.subhierarchies === null) {
          logMessage(
            LogLevels.WARNING,
            this.cfg,
            `Somehow, subhierarchies is null at ${name}`
          );
          continue;
        }
        logMessage(
          LogLevels.DEBUG,
          this.cfg,
          `${name} -> subhierarchy ${subh}`
        );
        const s_obj = inp.subhierarchies[subh];
        if (s_obj === null) {
          logMessage(
            LogLevels.DEBUG,
            this.cfg,
            `skipping null subhierarchy ${subh}`
          );
          continue;
        }
        if (this.subhierarchies === null) {
          this.subhierarchies = {};
        }
        logMessage(
          LogLevels.DEBUG,
          cfg,
          `recurse: new subhierarchy of ${name} ${subh}`
        );
        this.subhierarchies[subh] = new TutorialsHierarchy(s_obj, subh);
      }
    }
    logMessage(LogLevels.DEBUG, cfg, `hierarchy ${name} built`);
  }
}

async function apiGetTutorialsHierarchy(
  settings: ServerConnection.ISettings,
  cfg: INubladoConfigResponse
): Promise<TutorialsHierarchy> {
  /**
   * Make a request to our endpoint to get the tutorial hierarchy
   *
   * @param settings - the settings for the current notebook server
   *
   * @param cfg - the server configuration
   *
   * @returns a Promise resolved with the JSON response
   */
  // Fake out URL check in makeRequest
  const data = await apiRequest(
    PageConfig.getBaseUrl() + 'rubin/tutorials',
    { method: 'GET' },
    settings
  );

  logMessage(
    LogLevels.DEBUG,
    cfg,
    `Tutorial endpoint response: ${JSON.stringify(data, undefined, 2)}`
  );
  // Assure Typescript it will be the right shape.
  const u_d = data as unknown;
  const h_i = u_d as ITutorialsHierarchyResponse;
  const tut = new TutorialsHierarchy(h_i);
  logMessage(LogLevels.DEBUG, cfg, 'Created TutorialsHierarchy from response');
  logMessage(LogLevels.DEBUG, cfg, '==============================');
  return tut;
}

/**
 * Make a request to our endpoint to copy a file into place and open it
 *
 * @param settings - the settings for the current notebook server
 *
 * @param docManager - the application document manager
 *
 * @param entry - the entry corresponding to the file to work with
 *
 * @param cfg - the server configuration
 *
 * @returns a Promise resolved with the JSON response
 */
async function apiPostTutorialsEntry(
  settings: ServerConnection.ISettings,
  docManager: IDocumentManager,
  entry: TutorialsEntry,
  cfg: INubladoConfigResponse
): Promise<void> {
  // Fake out URL check in makeRequest
  logMessage(
    LogLevels.DEBUG,
    cfg,
    `Sending POST to tutorials endpoint with data ${JSON.stringify(
      entry,
      undefined,
      2
    )}`
  );

  try {
    const response = await ServerConnection.makeRequest(
      PageConfig.getBaseUrl() + 'rubin/tutorials',
      { method: 'POST', body: JSON.stringify(entry) },
      settings
    );

    if (response.status === 409) {
      // File exists; prompt user
      try {
        const verb = await overwriteDialog(entry.dest, docManager, cfg);
        logMessage(LogLevels.DEBUG, cfg, `Dialog result was ${verb}`);

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
        await apiPostTutorialsEntry(settings, docManager, newEntry, cfg);
      } catch (error) {
        logMessage(LogLevels.ERROR, cfg, `Error in overwrite dialog: ${error}`);
      }
    } else if (response.status === 307 || response.status === 200) {
      // File got copied.
      logMessage(LogLevels.DEBUG, cfg, `Opening file ${entry.dest}`);
      docManager.openOrReveal(entry.dest);
    } else {
      logMessage(
        LogLevels.WARNING,
        cfg,
        `Unexpected response status ${response.status}`
      );
    }
  } catch (error) {
    logMessage(
      LogLevels.ERROR,
      cfg,
      `Error in tutorials POST request: ${error}`
    );
  }
}

interface IDialogResult {
  button?: {
    label: string;
  };
}

async function overwriteDialog(
  dest: string,
  manager: IDocumentManager,
  cfg: INubladoConfigResponse
): Promise<string | void> {
  const dialogOptions = {
    title: 'Target file exists',
    body: `Overwrite file '${dest}' ?`,
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'OVERWRITE' })]
  };

  try {
    logMessage(LogLevels.DEBUG, cfg, 'Showing overwrite dialog');
    const result: IDialogResult = await showDialog(dialogOptions);
    if (!result) {
      logMessage(LogLevels.DEBUG, cfg, 'No result from overwriteDialog');
      return;
    }
    logMessage(LogLevels.DEBUG, cfg, 'Result from overwriteDialog: ', result);
    if (!result.button) {
      logMessage(LogLevels.DEBUG, cfg, 'No result.button from overwriteDialog');
      return;
    }
    if (result.button.label === 'OVERWRITE') {
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `Got result ${result.button.label} from overwriteDialog`
      );
      return result.button.label;
    }
    logMessage(LogLevels.DEBUG, cfg, 'Did not get overwriteDialog: OVERWRITE');
    return;
  } catch (error) {
    console.error(`Error showing overwrite dialog ${error}`);
    throw new Error(`Failed to show overwrite dialog: ${error}`);
  }
}

export function activateRSPTutorialsExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu,
  docManager: IDocumentManager,
  cfg: INubladoConfigResponse
): void {
  logMessage(LogLevels.INFO, cfg, 'rsp-tutorials: loading...');
  const svcManager = app.serviceManager;
  const settings = svcManager.serverSettings;

  function buildTutorialsMenu(
    name: string,
    hierarchy: ITutorialsHierarchyResponse,
    parentmenu: Menu | null,
    cfg: INubladoConfigResponse
  ): void {
    logMessage(LogLevels.DEBUG, cfg, `building tutorials menu for ${name}`);
    if (parentmenu === null) {
      // Set up submenu
      const { commands } = app;
      const tutorialsmenu = new Menu({ commands });
      tutorialsmenu.title.label = 'Tutorials';
      parentmenu = tutorialsmenu;
      logMessage(LogLevels.DEBUG, cfg, 'set up top level Tutorials menu');
      mainMenu.addMenu(tutorialsmenu);
    } else {
      logMessage(
        LogLevels.DEBUG,
        cfg,
        `supplied parent menu=${parentmenu.title.label}`
      );
    }
    const parent = parentmenu.title.label;
    logMessage(
      LogLevels.DEBUG,
      cfg,
      `building tutorials menu ${name}, parent=${parent}`
    );

    if (hierarchy.subhierarchies !== null) {
      // Recursively add submenus
      for (const subh in hierarchy.subhierarchies) {
        const s_obj = hierarchy.subhierarchies[subh];
        // Skip null or empty entries
        if (s_obj === null) {
          logMessage(LogLevels.DEBUG, cfg, `skipping empty hierarchy ${subh}`);
          continue;
        }
        if (s_obj.entries === null && s_obj.subhierarchies === null) {
          logMessage(
            LogLevels.DEBUG,
            cfg,
            `Skipping hierarchy ${subh} with no entries or subhierarchies`
          );
          continue;
        }
        logMessage(LogLevels.DEBUG, cfg, `adding submenu ${subh} to ${parent}`);
        const { commands } = app;
        const smenu = new Menu({ commands });
        smenu.title.label = subh;
        parentmenu.addItem({ submenu: smenu, type: 'submenu' });
        logMessage(LogLevels.DEBUG, cfg, `recurse: hierarchy ${subh}`);
        // Now recurse down new menu/subhierarchy
        buildTutorialsMenu(subh, s_obj, smenu, cfg);
        logMessage(
          LogLevels.DEBUG,
          cfg,
          `recursion done; emerged from ${subh}`
        );
      }
    }
    logMessage(LogLevels.DEBUG, cfg, `done with subhierarchies for ${name}`);

    if (hierarchy.entries !== null) {
      parentmenu.addItem({ type: 'separator' });
      for (const entry in hierarchy.entries) {
        const { commands } = app;
        const entry_obj = hierarchy.entries[entry];
        const cmdId = `${entry_obj.parent}/${entry_obj.menu_name}`;
        logMessage(
          LogLevels.DEBUG,
          cfg,
          `creating command ${cmdId} for entry ${JSON.stringify(
            entry,
            undefined,
            2
          )}`
        );
        commands.addCommand(cmdId, {
          label: entry,
          execute: () => {
            apiPostTutorialsEntry(settings, docManager, entry_obj, cfg);
          }
        });
        logMessage(LogLevels.DEBUG, cfg, `adding item ${cmdId} to ${parent}`);
        parentmenu.addItem({
          command: cmdId,
          type: 'command'
        });
      }
    }
    logMessage(LogLevels.DEBUG, cfg, `done with ${name}`);
  }

  (async () => {
    try {
      const res = await apiGetTutorialsHierarchy(settings, cfg);
      if (res) {
        const o_res = res as TutorialsHierarchy;
        buildTutorialsMenu('root', o_res, null, cfg);
      }
    } catch (error) {
      logMessage(
        LogLevels.ERROR,
        cfg,
        `Error loading tutorials hierarchy: ${error}`
      );
    }
  })();

  logMessage(LogLevels.INFO, cfg, 'rsp-tutorials: ...loaded.');
}

/**
 * Initialization data for the tutorials extension.
 */
const rspTutorialsExtension: JupyterFrontEndPlugin<void> = {
  activate: activateRSPTutorialsExtension,
  id: token.TUTORIALS_ID,
  requires: [IMainMenu, IDocumentManager],
  autoStart: false
};

export default rspTutorialsExtension;
