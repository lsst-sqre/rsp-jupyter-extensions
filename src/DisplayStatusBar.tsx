import * as React from 'react';

import { VDomModel, VDomRenderer } from '@jupyterlab/apputils';

import { TextItem } from '@jupyterlab/statusbar';

/**
 * A pure function for rendering the displayversion information.
 *
 * @param props: the props for rendering the component.
 *
 * @returns a tsx component for displaying version information.
 */
function DisplayStatusBarComponent(
  props: DisplayStatusBarComponent.IProps
): React.ReactElement<DisplayStatusBarComponent.IProps> {
  return <TextItem source={`${props.source}`} title={`${props.title}`} />;
}

/**
 * A namespace for DisplayStatusBarComponent
 */
export namespace DisplayStatusBarComponent {
  /**
   * The props for rendering the DisplayStatusBar.
   */
  export interface IProps {
    /**
     * Just two pieces of static information.
     */
    source: string;
    title: string;
  }
}

export class DisplayStatusBar extends VDomRenderer<VDomModel> {
  props: DisplayStatusBarComponent.IProps;
  /**
   * Create a new DisplayStatusBar widget.
   */
  constructor(props: DisplayStatusBarComponent.IProps) {
    super(new VDomModel());
    this.props = props;
  }

  /**
   * Render the display Lab version widget.
   */
  render(): JSX.Element | null {
    if (!this.props) {
      return null;
    }
    return (
      <DisplayStatusBarComponent
        source={this.props.source}
        title={this.props.title}
      />
    );
  }

  /**
   * Dispose of the item.
   */
  dispose(): void {
    super.dispose();
  }
}

export namespace DisplayStatusBar {}

export default DisplayStatusBar;
