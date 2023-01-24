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
function DisplayLabVersionComponent(
  props: DisplayLabVersionComponent.IProps
): React.ReactElement<DisplayLabVersionComponent.IProps> {
  return <TextItem source={`${props.source}`} title={`${props.title}`} />;
}

/**
 * A namespace for DisplayLabVersionComponent
 */
export namespace DisplayLabVersionComponent {
  /**
   * The props for rendering the DisplayLabVersion.
   */
  export interface IProps {
    /**
     * Just two pieces of static information.
     */
    source: string;
    title: string;
  }
}

export class DisplayLabVersion extends VDomRenderer<VDomModel> {
  props: DisplayLabVersionComponent.IProps;
  /**
   * Create a new DisplayLabVersion widget.
   */
  constructor(props: DisplayLabVersionComponent.IProps) {
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
      <DisplayLabVersionComponent
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

export namespace DisplayLabVersion {}

export default DisplayLabVersion;
