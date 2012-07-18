from os.path import join, exists, dirname
from os import makedirs
import datetime
import operator
from Acquisition import aq_inner
from AccessControl import getSecurityManager

from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName

import zope.component

from webassets import Bundle, Environment
from jsmin import jsmin
from .env import IWebAssetsEnvironment

try:
    from Products.ResourceRegistries.browser.scripts import ScriptsView as BaseScriptsView
    from Products.ResourceRegistries.browser.styles import StylesView as BaseStylesView
    HAS_RR = True
except ImportError:
    HAS_RR = False
    BaseScriptsView = BaseStylesView = BrowserView

def is_anonymous():
    user = getSecurityManager().getUser()
    return bool(user.getUserName() == 'Anonymous User')

def check(bundle, context):
    if bundle.extra_data.get('authenticated', False):
        return not is_anonymous()
    exp = bundle.extra_data.get('expression', False)
    if not exp:
        return True
    # XXX evaluateExpression does not need to be
    # called from the tool but we don't want to
    # duplicate the code for now
    portal_css = getToolByName(context, 'portal_css')
    return portal_css.evaluateExpression(exp, context)

TURNED_ON = False

class ScriptsView(BaseScriptsView):

    def scripts(self):
        if not TURNED_ON:
            return super(ScriptsView, self).scripts()
        env = zope.component.getUtility(IWebAssetsEnvironment)
        context = aq_inner(self.context)
        scripts = []
        for name, bundle in env._named_bundles.iteritems():
            if not name.startswith('js-'):
                continue
            if not check(bundle, context):
                continue
            scripts.append({'inline': False,
                            'conditionalcomment' : '',
                            'src': bundle.urls()[0]})
        scripts.sort(key=operator.itemgetter('src'))
        return scripts

class StylesView(BaseStylesView):

    def styles(self):
        if not TURNED_ON:
            return super(StylesView, self).styles()
        env = zope.component.getUtility(IWebAssetsEnvironment)
        context = aq_inner(self.context)

        styles = []        

        site_url = 'http://localhost:8080/Plone'

        for name, bundle in env._named_bundles.iteritems():
            if not name.startswith('css-'):
                continue
            if not check(bundle, context):
                continue
            styles.append({'rendering': 'link',
                        'media': bundle.extra_data.get('media', None),
                        'rel': 'stylesheet',
                        'rendering': bundle.extra_data.get('rendering', 'link'),
                        'title': None,
                        'conditionalcomment' : '',
                        'src': site_url + bundle.urls()[0]})
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

    def __call__(self):
        start = now()
        context = aq_inner(self.context)

        env = zope.component.getUtility(IWebAssetsEnvironment)

        # export portal tool content to filesystem and register as assets
        for info in [CSS, JS]:
            tool = getToolByName(context, info.oid)

# XXX allow other themes
            theme = 'Plone Default'

            #saved_debug_mode = tool.getDebugMode()
            tool.setDebugMode(False)
            resources = tool.getResourcesDict()
            print
            for i, entry in enumerate(tool.getCookedResources(theme)):

                # get groups of resources
                # the groups are defined by the resource attributes
                # see `compareResources`-method in individual tools
                sheets = tool.concatenatedResourcesByTheme.get(theme, {})
                subentries = sheets.get(entry.getId())
                bundle_sheets = []

                # get individual resources of a group
                for eid in subentries:
                    print "  - ", eid
                    file_resource = join(env.directory, info.suffix, eid)
                    if not exists(dirname(file_resource)):
                        makedirs(dirname(file_resource))
                    f = open(file_resource, 'w')
                    content = tool.getResourceContent(
                                eid, context, original=True, theme=theme)

                    resource = resources[eid]
                    if info.suffix == 'css':
                        m = resource.getMedia()
                        if m:
                            content = '@media %s {\n%s\n}\n' % (m, content)
                    elif info.suffix == 'js':
                        if resource.getCompression() != 'none':
                            content = jsmin(content)
            
                    f.write(content.encode('utf-8'))
                    f.close()
                    # XXX check for caching and merging allowed
                    bundle_sheets.append('%s/%s' % (info.suffix, eid))

                # generate asset and register with bundle
#                if False:
#                    bundle = Bundle(*bundle_sheets,
#                                    output='gen/%s-%s' %  (i, entry.getId()))
#                elif entry.getCompression() == 'none' or \
#                    (info.suffix == 'js' and entry.getCompression() == 'safe'):
                if entry.getCompression() == 'none':
                    bundle = Bundle(*bundle_sheets,
                                    output='gen/packed%s.%s' %  (i, info.suffix))
                else:
                    bundle = Bundle(*bundle_sheets,
                                    filters=info.filters,
                                    output='gen/packed%s.%s' %  (i, info.suffix))
                bundle.extra_data['authenticated'] = entry.getAuthenticated()
                bundle.extra_data['expression'] = entry.getCookedExpression()
                if info.suffix == 'css':
                    bundle.extra_data['media'] = entry.getMedia()
                    bundle.extra_data['rendering'] = entry.getRendering()
                env.register('%s-%s' % (info.suffix, i), bundle)
            #tool.setDebugMode(saved_debug_mode)
        return "Done!\nTook: %s " % (now() - start)
