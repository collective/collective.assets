import logging

import zope.component
from .interfaces import IWebAssetsEnvironment

LOG = logging.getLogger('assets')

def generate_assets(event):
    env = zope.component.getUtility(IWebAssetsEnvironment)
    if not len(env):
        site = zope.component.hooks.getSite()
        if site is None:
            # No plone Site
            return
        generateview = zope.component.queryMultiAdapter(
                (site, event.request), name="generate-assets")
        LOG.warn('No assets found. Generating them.')
        generateview.generate()

