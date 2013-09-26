from os.path import join, exists, dirname
from os import makedirs
import datetime
import operator
import logging
from Acquisition import aq_inner
from AccessControl import getSecurityManager

from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage

import zope.component
from zope.component.hooks import getSite

from webassets import Bundle
from webassets.env import RegisterError
from jsmin import jsmin
from .interfaces import IWebAssetsEnvironment

LOG = logging.getLogger('assets')

try:
    from Products.ResourceRegistries.browser.scripts import ScriptsView as BaseScriptsView
    from Products.ResourceRegistries.browser.styles import StylesView as BaseStylesView
    HAS_RR = True
except ImportError:     # pragma: no cover
    HAS_RR = False
    BaseScriptsView = BaseStylesView = BrowserView


def check(bundle, context):
    if bundle.extra.get('authenticated', False):
        portal_state = context.restrictedTraverse('@@plone_portal_state')
        return not portal_state.anonymous()
    exp = bundle.extra.get('expression', False)
    if not exp:
        return True
    # XXX evaluateExpression does not need to be
    # called from the tool but we don't want to
    # duplicate the code for now
    portal_css = getToolByName(context, 'portal_css')
    return portal_css.evaluateExpression(exp, context)

class ScriptsView(BaseScriptsView):

    def scripts(self):
        env = zope.component.getUtility(IWebAssetsEnvironment)
        if not env.config.get('active', False):
            return super(ScriptsView, self).scripts()
        context = aq_inner(self.context)
        site_url = getSite().absolute_url()
        scripts = []
        for name, bundle in env._named_bundles.iteritems():
            if not name.startswith('js-'):
                continue
            if not check(bundle, context):
                continue
            for url in bundle.urls():
                scripts.append({'inline': False,
                                'conditionalcomment' : '',
                                'src': site_url + url})
        scripts.sort(key=operator.itemgetter('src'))
        return scripts

class StylesView(BaseStylesView):

    def styles(self):
        env = zope.component.getUtility(IWebAssetsEnvironment)
        if not env.config.get('active', False):
            return super(StylesView, self).styles()
        context = aq_inner(self.context)

        site_url = getSite().absolute_url()
        styles = []
        for name, bundle in env._named_bundles.iteritems():
            if not name.startswith('css-'):
                continue
            if not check(bundle, context):
                continue
            for url in bundle.urls():
                styles.append({'rendering': 'link',
                    'media': bundle.extra.get('media', 'screen'),
                    'rel': 'stylesheet',
                    'rendering': bundle.extra.get('rendering', 'link'),
                    'title': None,
                    'conditionalcomment' : '',
                    'src': site_url + url})
        styles.sort(key=operator.itemgetter('src'))
        return styles


class PortalCSS(object):

    oid = 'portal_css'
    suffix = 'css'
    filters = 'cssmin'

CSS = PortalCSS()

class PortalJavaScripts(object):

    oid = 'portal_javascripts'
    suffix = 'js'
    filters = 'jsmin'

JS = PortalJavaScripts()

now = lambda: datetime.datetime.now()


class GenerateAssetsView(BrowserView):

    def __call__(self, force='true'):
        context = aq_inner(self.context)
        env = zope.component.getUtility(IWebAssetsEnvironment)
        if force == 'true':
            env.clear()

        start = now()
        # export portal tool content to filesystem and register as assets
        for info in [CSS, JS]:
            tool = getToolByName(context, info.oid)
            tool.setDebugMode(False)
            theme = tool.getCurrentSkinName()
            resources = tool.getResourcesDict()
            for i, entry in enumerate(tool.getCookedResources(theme)):

                # get groups of resources
                # the groups are defined by the resource attributes
                # see `compareResources`-method in individual tools
                sheets = tool.concatenatedResourcesByTheme.get(theme, {})
                subentries = sheets.get(entry.getId())
                bundle_sheets = []

                # get individual resources of a group and write them
                # to the file system
                for eid in subentries:
                    resource = resources[eid]
                    if resource.getConditionalcomment():
                        LOG.debug('skipping %s', eid)
                        continue
                    LOG.debug('merging %s', eid)
                    file_resource = join(env.directory, info.suffix, eid)
                    if not exists(dirname(file_resource)):
                        makedirs(dirname(file_resource))
                    f = open(file_resource, 'w')
                    content = tool.getResourceContent(
                                eid, context, original=True, theme=theme)

                    if info.suffix == 'css':
                        m = resource.getMedia()
                        if m:
                            content = '@media %s {\n%s\n}\n' % (m, content)

                    f.write(content.encode('utf-8'))
                    f.close()
                    bundle_sheets.append('%s/%s' % (info.suffix, eid))
                if not bundle_sheets:
                    continue

                # generate asset and register with bundle
                if entry.getCompression() == 'none':
                    bundle = Bundle(*bundle_sheets,
                                    output='gen/packed%s.%s' %  (i, info.suffix))
                else:
                    bundle = Bundle(*bundle_sheets,
                                    filters=info.filters,
                                    output='gen/packed%s.%s' %  (i, info.suffix))
                bundle.extra['authenticated'] = entry.getAuthenticated()
                bundle.extra['expression'] = entry.getCookedExpression()
                if info.suffix == 'css':
                    bundle.extra['media'] = entry.getMedia()
                    bundle.extra['rendering'] = entry.getRendering()
                try:
                    env.register('%s-%s' % (info.suffix, i), bundle)
                except RegisterError:
                    return ("Failed!\nBundle %s-%s already registered. "
                            "Try force mode to recreate environment.") % (
                            info.suffix, i)
        msg = "Done!\nTook: %s " % (now() - start)
        IStatusMessage(self.request).add(msg)
        return msg

