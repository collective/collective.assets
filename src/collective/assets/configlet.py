from zope.component import adapts, queryUtility, queryMultiAdapter
from zope.interface import Interface, implements
from zope.schema import Bool
from persistent import Persistent

from Products.CMFDefault.formlib.schema import SchemaAdapterBase
from Products.CMFPlone.interfaces import IPloneSiteRoot
from plone.app.controlpanel.form import ControlPanelForm

from zope.formlib.form import FormFields, action

from collective.assets import CollectiveAssetsMessageFactory as _
from collective.assets.interfaces import IAssetsSchema, IAssetsConfig


class AssetsConfig(Persistent):

    implements(IAssetsConfig)

    def __init__(self):
        self.active = False


class AssetsControlPanelAdapter(SchemaAdapterBase):
    adapts(IPloneSiteRoot)
    implements(IAssetsSchema)

    def getActive(self):
        util = queryUtility(IAssetsConfig)
        return getattr(util, 'active', '')

    def setActive(self, value):
        util = queryUtility(IAssetsConfig)
        if util is not None:
            util.active = value

    active = property(getActive, setActive)


class AssetsControlPanel(ControlPanelForm):

    form_fields = FormFields(IAssetsSchema)

    label = _('label_assets_settings', default='Assets settings')
    description = _('help_assets_settings',
                     default='Settings to enable and configure web assets.')
    form_name = _('label_assets_settings', default='Assets settings')

    @action(_(u'label_generate', default=u'Generate Assets'),
            name=u'generate')
    def handle_generate_action(self, action, data):
        generateview = queryMultiAdapter((self.context, self.request),
                                         name="generate-assets")
        return generateview()
