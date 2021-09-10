class DisplayVersion_handler(APIHandler):
    """
    DisplayVersion Handler.  Return the JSON representation of our
    Lab version information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version_config={}
        for i in ["JUPYTER_IMAGE", "IMAGE_DESCRIPTION", "IMAGE_DIGEST"]:
            self.version_config[i.lower()] = self._files_then_env(i)
        self.version_config["label"] = self._label_from_fields(
            self.version_config)

    def get(self):
        """
        """
        self.log.info("Sending Display Version settings")
        self.finish(json.dumps(self.version_config))


    def _files_then_env(self, symbol):
        """Try to extract a symbol.  First use the path at which it should be
        mounted into the container.  If that doesn't exist or isn't
        readable, try the environment variable of the same name.  If
        neither of those works, return the empty string.
        """
        basedir = "/opt/lsst/software/jupyterlab/environment"
        val = ""
        try:
            fn = os.path.join(basedir, symbol)
            with open(fn, "r") as f:
                val = f.read()
        except Exception as e:
            self.log.warning(f"Could not read from {fn}: {e}; trying env var.")
            val = os.getenv(symbol, "")
        return val


    def _label_from_fields(self, version_config):
        # Parse the image ref into fields we want to display; do the work
        #  here and return an object with computed fields to our caller so
        #  the UI side can be very dumb.

        # Start with the fields that came in from the Lab container context
        # Get rid of host/owner if any in image reference
        display_desc = version_config["image_description"]
        display_name = version_config["jupyter_image"].split("/")[-1]
        display_hash = version_config["image_digest"]

        # If we have a description, put parens around the image name; if we
        #  don't, use the image name as our main text, since description is
        #  empty.
        if display_desc != "":
            display_name = f" ({display_name})"

        # If we have a digest, format it for display (remove algorithm and
        #  truncate to 8 characters, then add an ellipsis and put the whole
        #  thing in square brackets).
        if display_hash != "":
            trunc_hash = (display_hash.split(":")[-1])[:8]
            display_hash = f" [ {trunc_hash}... ] "

        # Then just concatenate them all together
        label=f"{display_desc}{display_name}{display_hash}"
        return label


