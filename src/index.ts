import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { requestAPI } from './handler';

/**
 * Initialization data for the rubin-rsp-jupyter-extensions extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'rubin-rsp-jupyter-extensions:plugin',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension rubin-rsp-jupyter-extensions is activated!');

    requestAPI<any>('get_example')
      .then(data => {
        console.log(data);
      })
      .catch(reason => {
        console.error(
          `The rubin_rsp_jupyter_extensions server extension appears to be missing.\n${reason}`
        );
      });
  }
};

export default plugin;
