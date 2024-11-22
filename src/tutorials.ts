// Copyright (c) LSST DM/SQuaRE
// Distributed under the terms of the MIT License.

import {
    JupyterFrontEnd,
    JupyterFrontEndPlugin
  } from '@jupyterlab/application';

import { PageConfig } from '@jupyterlab/coreutils';

import { ServerConnection } from '@jupyterlab/services';

import { CommandRegistry } from '@lumino/commands';

import { Menu } from '@lumino/widgets';

//import { ServiceManager, ServerConnection } from '@jupyterlab/services';
import { IMainMenu } from '@jupyterlab/mainmenu';

import * as token from './tokens';

export namespace CommandIDs {
  export const rubintutorials = 'rubintutorials';
  export const rubintutorialsnull = 'rubintutorialsnull'
}

enum Actions {
    COPY="copy",
    FETCH="fetch",
}

enum Dispositions {
    PROMPT="prompt",
    OVERWRITE="overwrite",
    ABORT="abort",
}

interface ITutorialsEntryResponse {
    menu_name: string;
    action: Actions;
    disposition: Dispositions;
    parent: string;
    src: string;
    dest: string;
}

class TutorialsEntry implements ITutorialsEntryResponse{
    menu_name: string;
    action: Actions;
    disposition: Dispositions;
    parent: string;
    src: string;
    dest: string;

    constructor(inp: ITutorialsEntryResponse) {
        this.menu_name=inp.menu_name,
        this.action=inp.action,
        this.disposition=inp.disposition,
        this.parent=inp.parent,
        this.src=inp.src,
        this.dest=inp.dest
     }
}

interface ITutorialsHierarchyResponse {
    entries: { [name:string]: ITutorialsEntryResponse } | null;
    subhierarchies: { [name:string]: ITutorialsHierarchyResponse } | null;
}

class TutorialsHierarchy implements ITutorialsHierarchyResponse {
    entries: { [name: string]: TutorialsEntry } | null = null;
    subhierarchies: { [name: string]: TutorialsHierarchy } | null = null;

    constructor(inp: ITutorialsHierarchyResponse) {
        console.log(`Building hierarchy`)
        if (inp.entries != null ) {
            for (const entry in inp.entries) {
                const e_obj = inp.entries[entry]
                if (e_obj == null) {
                    console.log(`skipping null entry ${entry}`)
                    continue
                }
                if (this.entries == null) {
                    this.entries = {}
                }
                console.log(`adding entry ${entry}: ${JSON.stringify(e_obj, undefined, 2)}`)
                this.entries[entry] = new TutorialsEntry(e_obj)
            }

        }
        if (inp.subhierarchies != null) {
            if (inp.subhierarchies == null) {
                console.log("WTF, man, inp.subhierarchies is null");
            } else {
                for (const subh in inp.subhierarchies) {
                    const s_obj=inp.subhierarchies[subh];
                    if (s_obj == null) {
                     console.log(`skipping null subhierarchy ${subh}`)
                     continue
                    }
                    if (this.subhierarchies == null) {
                         this.subhierarchies = {}
                     }
                    console.log(`adding new subhierarchy ${subh}`)
                    this.subhierarchies[subh] = new TutorialsHierarchy(s_obj)
                }
            }
        }
    }
}

function apiGetTutorialsHierarchy(
    settings: ServerConnection.ISettings
  ): Promise<TutorialsHierarchy> {
    /**
     * Make a request to our endpoint to get the tutorial hierarchy
     *
     * @param url - the path for the displayversion extension
     *
     * @param init - The GET for the extension
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
      return (response.json().then(data=> {
        console.log(`Response: ${JSON.stringify(data, undefined, 2)}`)
        const h_i = data as ITutorialsHierarchyResponse
        const tut = new TutorialsHierarchy(h_i)
        return tut
      }))
    })
}

function apiPostTutorialsEntry(
    settings: ServerConnection.ISettings,
    entry: TutorialsEntry
): Promise<void> {

    return new Promise((res, rej) => {
        /* Nothing */
      });
}

export function activateRSPTutorialsExtension(
  app: JupyterFrontEnd,
  mainMenu: IMainMenu
): void {
    console.log('rsp-tutorials: loading...');
    const svcManager = app.serviceManager;
    const settings = svcManager.serverSettings;

    function buildTutorialsMenu(
        hierarchy: ITutorialsHierarchyResponse,
        parentmenu: Menu | null
    ): void {
        const { commands } = app;

        if (parentmenu == null) {
            // Set up submenu
            const tutorialsmenu = new Menu({commands})
            tutorialsmenu.title.label = 'Tutorials'
            parentmenu = tutorialsmenu
        }
        console.log(`building tutorials menu, parent=${parentmenu.title.caption}`)

        if (hierarchy.subhierarchies != null) {
            // Recursively add submenus
            for (const subh in hierarchy.subhierarchies) {
                const s_obj = hierarchy.subhierarchies[subh]
                // Skip null or empty entries
                if (s_obj == null) {
                    continue
                }
                if ((s_obj.entries == null) && (s_obj.subhierarchies == null)) {
                    continue
                }
                console.log(`adding submenu ${subh}, parent ${parentmenu.title.label}`)
                const smenu = new Menu({commands})
                smenu.title.label = subh
                parentmenu.addItem({submenu: smenu, type: "submenu"})
                console.log(`recurse: hierarchy ${subh}`)
                // Now recurse down new menu/subhierarchy
                buildTutorialsMenu(
                    hierarchy=s_obj,
                    parentmenu=smenu
                )
            }
        }
        if (hierarchy.entries != null) {
            for (const entry in hierarchy.entries) {
                const entry_obj=hierarchy.entries[entry]
                console.log(`adding entry ${JSON.stringify(entry_obj, undefined, 2)}`)
                const postcommandregistry = new CommandRegistry()
                postcommandregistry.addCommand(
                    CommandIDs.rubintutorials, {
                        caption: entry,
                        execute: () => {
                            apiPostTutorialsEntry(
                                settings,
                                entry_obj,
                            )
                        }
                    }
                )

                parentmenu.addItem({
                    command: CommandIDs.rubintutorials,
                    // caption: entry,
                    type: "command",
                })
            }
        }

    }

    apiGetTutorialsHierarchy(settings).then(res => {
        if (res) {
            const o_res = res as TutorialsHierarchy
            buildTutorialsMenu(o_res,null)
        }
    })

    console.log('rsp-tutorials: ...loaded.')
}

/**
 * Initialization data for the jupyterlab-lsstquery extension.
 */
const rspTutorialsExtension: JupyterFrontEndPlugin<void> = {
    activate: activateRSPTutorialsExtension,
    id: token.TUTORIALS_ID,
    requires: [IMainMenu],
    autoStart: false
  };

  export default rspTutorialsExtension;