import logging
import os
import traceback
from math import floor
from typing import List, Tuple

from PyQt5.QtWidgets import QApplication, QStyleFactory

from bauh import ROOT_DIR
from bauh.api.abstract.controller import SoftwareManager
from bauh.api.abstract.view import ViewComponent, TabComponent, InputOption, TextComponent, MultipleSelectComponent, \
    PanelComponent, FormComponent, TabGroupComponent, SingleSelectComponent, SelectViewType, TextInputComponent, \
    FileChooserComponent
from bauh.view.core import config, timeshift
from bauh.view.core.config import read_config
from bauh.view.util import translation
from bauh.view.util.translation import I18n


class GenericSettingsManager:

    def __init__(self, managers: List[SoftwareManager], working_managers: List[SoftwareManager],
                 logger: logging.Logger, i18n: I18n):
        self.i18n = i18n
        self.managers = managers
        self.working_managers = working_managers
        self.logger = logger

    def get_settings(self, screen_width: int, screen_height: int) -> ViewComponent:
        tabs = list()

        gem_opts, def_gem_opts, gem_tabs = [], set(), []

        for man in self.managers:
            if man.can_work():
                man_comp = man.get_settings(screen_width, screen_height)
                modname = man.__module__.split('.')[-2]
                icon_path = "{r}/gems/{n}/resources/img/{n}.svg".format(r=ROOT_DIR, n=modname)

                if man_comp:
                    tab_name = self.i18n.get('gem.{}.label'.format(modname), modname.capitalize())
                    gem_tabs.append(TabComponent(label=tab_name, content=man_comp, icon_path=icon_path, id_=modname))

                opt = InputOption(label=self.i18n.get('gem.{}.label'.format(modname), modname.capitalize()),
                                  tooltip=self.i18n.get('gem.{}.info'.format(modname)),
                                  value=modname,
                                  icon_path='{r}/gems/{n}/resources/img/{n}.svg'.format(r=ROOT_DIR, n=modname))
                gem_opts.append(opt)

                if man.is_enabled() and man in self.working_managers:
                    def_gem_opts.add(opt)

        core_config = read_config()

        if gem_opts:
            type_help = TextComponent(html=self.i18n['core.config.types.tip'])
            gem_opts.sort(key=lambda o: o.value)
            gem_selector = MultipleSelectComponent(label=None,
                                                   tooltip=None,
                                                   options=gem_opts,
                                                   max_width=floor(screen_width * 0.22),
                                                   default_options=def_gem_opts,
                                                   id_="gems")
            tabs.append(TabComponent(label=self.i18n['core.config.tab.types'],
                                     content=PanelComponent([type_help, FormComponent([gem_selector], spaces=False)]),
                                     id_='core.types'))

        tabs.append(self._gen_general_settings(core_config, screen_width, screen_height))
        tabs.append(self._gen_ui_settings(core_config, screen_width, screen_height))
        tabs.append(self._gen_tray_settings(core_config, screen_width, screen_height))
        tabs.append(self._gen_adv_settings(core_config, screen_width, screen_height))

        bkp_settings = self._gen_backup_settings(core_config, screen_width, screen_height)

        if bkp_settings:
            tabs.append(bkp_settings)

        for tab in gem_tabs:
            tabs.append(tab)

        return TabGroupComponent(tabs)

    def _gen_adv_settings(self, core_config: dict, screen_width: int, screen_height: int) -> TabComponent:
        default_width = floor(0.22 * screen_width)

        input_data_exp = TextInputComponent(label=self.i18n['core.config.mem_cache.data_exp'],
                                            tooltip=self.i18n['core.config.mem_cache.data_exp.tip'],
                                            value=str(core_config['memory_cache']['data_expiration']),
                                            only_int=True,
                                            max_width=default_width,
                                            id_="data_exp")

        input_icon_exp = TextInputComponent(label=self.i18n['core.config.mem_cache.icon_exp'],
                                            tooltip=self.i18n['core.config.mem_cache.icon_exp.tip'],
                                            value=str(core_config['memory_cache']['icon_expiration']),
                                            only_int=True,
                                            max_width=default_width,
                                            id_="icon_exp")

        select_trim_up = self._gen_select(label=self.i18n['core.config.trim.after_upgrade'],
                                          tip=self.i18n['core.config.trim.after_upgrade.tip'],
                                          value=core_config['disk']['trim']['after_upgrade'],
                                          max_width=default_width,
                                          opts=[(self.i18n['yes'].capitalize(), True, None),
                                                (self.i18n['no'].capitalize(), False, None),
                                                (self.i18n['ask'].capitalize(), None, None)],
                                          id_='trim_after_upgrade')

        select_dep_check = self._gen_bool_component(label=self.i18n['core.config.system.dep_checking'],
                                                    tooltip=self.i18n['core.config.system.dep_checking.tip'],
                                                    value=core_config['system']['single_dependency_checking'],
                                                    max_width=default_width,
                                                    id_='dep_check')

        select_dmthread = self._gen_bool_component(label=self.i18n['core.config.download.multithreaded'],
                                                   tooltip=self.i18n['core.config.download.multithreaded.tip'],
                                                   id_="down_mthread",
                                                   max_width=default_width,
                                                   value=core_config['download']['multithreaded'])

        sub_comps = [FormComponent([select_dmthread, select_trim_up, select_dep_check, input_data_exp, input_icon_exp], spaces=False)]
        return TabComponent(self.i18n['core.config.tab.advanced'].capitalize(), PanelComponent(sub_comps), None, 'core.adv')

    def _gen_tray_settings(self, core_config: dict, screen_width: int, screen_height: int) -> TabComponent:
        default_width = floor(0.22 * screen_width)

        input_update_interval = TextInputComponent(label=self.i18n['core.config.updates.interval'].capitalize(),
                                                   tooltip=self.i18n['core.config.updates.interval.tip'],
                                                   only_int=True,
                                                   value=str(core_config['updates']['check_interval']),
                                                   max_width=default_width,
                                                   id_="updates_interval")

        allowed_exts = {'png', 'svg', 'jpg', 'jpeg', 'ico', 'xpm'}
        select_def_icon = FileChooserComponent(id_='def_icon',
                                               label=self.i18n["core.config.ui.tray.default_icon"].capitalize(),
                                               tooltip=self.i18n["core.config.ui.tray.default_icon.tip"].capitalize(),
                                               file_path=str(core_config['ui']['tray']['default_icon']) if core_config['ui']['tray']['default_icon'] else None,
                                               max_width=default_width,
                                               allowed_extensions=allowed_exts)

        select_up_icon = FileChooserComponent(id_='up_icon',
                                              label=self.i18n["core.config.ui.tray.updates_icon"].capitalize(),
                                              tooltip=self.i18n["core.config.ui.tray.updates_icon.tip"].capitalize(),
                                              file_path=str(core_config['ui']['tray']['updates_icon']) if core_config['ui']['tray']['updates_icon'] else None,
                                              max_width=default_width,
                                              allowed_extensions=allowed_exts)

        sub_comps = [FormComponent([input_update_interval, select_def_icon, select_up_icon], spaces=False)]
        return TabComponent(self.i18n['core.config.tab.tray'].capitalize(), PanelComponent(sub_comps), None, 'core.tray')

    def _gen_ui_settings(self, core_config: dict, screen_width: int, screen_height: int) -> TabComponent:
        default_width = floor(0.11 * screen_width)

        select_hdpi = self._gen_bool_component(label=self.i18n['core.config.ui.hdpi'],
                                               tooltip=self.i18n['core.config.ui.hdpi.tip'],
                                               value=bool(core_config['ui']['hdpi']),
                                               max_width=default_width,
                                               id_='hdpi')

        select_ascale = self._gen_bool_component(label=self.i18n['core.config.ui.auto_scale'],
                                                 tooltip=self.i18n['core.config.ui.auto_scale.tip'].format('QT_AUTO_SCREEN_SCALE_FACTOR'),
                                                 value=bool(core_config['ui']['auto_scale']),
                                                 max_width=default_width,
                                                 id_='auto_scale')

        cur_style = QApplication.instance().style().objectName().lower() if not core_config['ui']['style'] else core_config['ui']['style']
        style_opts = [InputOption(label=s.capitalize(), value=s.lower()) for s in QStyleFactory.keys()]
        select_style = SingleSelectComponent(label=self.i18n['style'].capitalize(),
                                             options=style_opts,
                                             default_option=[o for o in style_opts if o.value == cur_style][0],
                                             type_=SelectViewType.COMBO,
                                             max_width=default_width,
                                             id_="style")

        input_maxd = TextInputComponent(label=self.i18n['core.config.ui.max_displayed'].capitalize(),
                                        tooltip=self.i18n['core.config.ui.max_displayed.tip'].capitalize(),
                                        only_int=True,
                                        id_="table_max",
                                        max_width=default_width,
                                        value=str(core_config['ui']['table']['max_displayed']))

        select_dicons = self._gen_bool_component(label=self.i18n['core.config.download.icons'],
                                                 tooltip=self.i18n['core.config.download.icons.tip'],
                                                 id_="down_icons",
                                                 max_width=default_width,
                                                 value=core_config['download']['icons'])

        sub_comps = [FormComponent([select_hdpi, select_ascale, select_dicons, select_style, input_maxd], spaces=False)]
        return TabComponent(self.i18n['core.config.tab.ui'].capitalize(), PanelComponent(sub_comps), None, 'core.ui')

    def _gen_general_settings(self, core_config: dict, screen_width: int, screen_height: int) -> TabComponent:
        default_width = floor(0.11 * screen_width)

        locale_opts = [InputOption(label=self.i18n['locale.{}'.format(k)].capitalize(), value=k) for k in translation.get_available_keys()]

        current_locale = None

        if core_config['locale']:
            current_locale = [l for l in locale_opts if l.value == core_config['locale']]

        if not current_locale:
            if self.i18n.current_key:
                current_locale = [l for l in locale_opts if l.value == self.i18n.current_key]

            if not current_locale:
                current_locale = [l for l in locale_opts if l.value == self.i18n.default_key]

        current_locale = current_locale[0] if current_locale else None

        select_locale = SingleSelectComponent(label=self.i18n['core.config.locale.label'],
                                              options=locale_opts,
                                              default_option=current_locale,
                                              type_=SelectViewType.COMBO,
                                              max_width=default_width,
                                              id_='locale')

        select_store_pwd = self._gen_bool_component(label=self.i18n['core.config.store_password'].capitalize(),
                                                    tooltip=self.i18n['core.config.store_password.tip'].capitalize(),
                                                    id_="store_pwd",
                                                    max_width=default_width,
                                                    value=bool(core_config['store_root_password']))

        select_sysnotify = self._gen_bool_component(label=self.i18n['core.config.system.notifications'].capitalize(),
                                                    tooltip=self.i18n['core.config.system.notifications.tip'].capitalize(),
                                                    value=bool(core_config['system']['notifications']),
                                                    max_width=default_width,
                                                    id_="sys_notify")

        select_sugs = self._gen_bool_component(label=self.i18n['core.config.suggestions.activated'].capitalize(),
                                               tooltip=self.i18n['core.config.suggestions.activated.tip'].capitalize(),
                                               id_="sugs_enabled",
                                               max_width=default_width,
                                               value=bool(core_config['suggestions']['enabled']))

        inp_sugs = TextInputComponent(label=self.i18n['core.config.suggestions.by_type'],
                                      tooltip=self.i18n['core.config.suggestions.by_type.tip'],
                                      value=str(core_config['suggestions']['by_type']),
                                      only_int=True,
                                      max_width=default_width,
                                      id_="sugs_by_type")

        sub_comps = [FormComponent([select_locale, select_store_pwd, select_sysnotify, select_sugs, inp_sugs], spaces=False)]
        return TabComponent(self.i18n['core.config.tab.general'].capitalize(), PanelComponent(sub_comps), None, 'core.gen')

    def _gen_bool_component(self, label: str, tooltip: str, value: bool, id_: str, max_width: int = 200) -> SingleSelectComponent:
        opts = [InputOption(label=self.i18n['yes'].capitalize(), value=True),
                InputOption(label=self.i18n['no'].capitalize(), value=False)]

        return SingleSelectComponent(label=label,
                                     options=opts,
                                     default_option=[o for o in opts if o.value == value][0],
                                     type_=SelectViewType.RADIO,
                                     tooltip=tooltip,
                                     max_per_line=len(opts),
                                     max_width=max_width,
                                     id_=id_)

    def _save_settings(self, general: PanelComponent,
                       advanced: PanelComponent,
                       backup: PanelComponent,
                       ui: PanelComponent,
                       tray: PanelComponent,
                       gems_panel: PanelComponent) -> Tuple[bool, List[str]]:
        core_config = config.read_config()

        # general
        general_form = general.components[0]

        locale = general_form.get_component('locale').get_selected()

        if locale != self.i18n.current_key:
            core_config['locale'] = locale

        core_config['system']['notifications'] = general_form.get_component('sys_notify').get_selected()
        core_config['suggestions']['enabled'] = general_form.get_component('sugs_enabled').get_selected()
        core_config['store_root_password'] = general_form.get_component('store_pwd').get_selected()

        sugs_by_type = general_form.get_component('sugs_by_type').get_int_value()
        core_config['suggestions']['by_type'] = sugs_by_type

        # advanced
        adv_form = advanced.components[0]

        download_mthreaded = adv_form.get_component('down_mthread').get_selected()
        core_config['download']['multithreaded'] = download_mthreaded

        single_dep_check = adv_form.get_component('dep_check').get_selected()
        core_config['system']['single_dependency_checking'] = single_dep_check

        data_exp = adv_form.get_component('data_exp').get_int_value()
        core_config['memory_cache']['data_expiration'] = data_exp

        icon_exp = adv_form.get_component('icon_exp').get_int_value()
        core_config['memory_cache']['icon_expiration'] = icon_exp

        core_config['disk']['trim']['after_upgrade'] = adv_form.get_component('trim_after_upgrade').get_selected()

        # backup
        if backup:
            bkp_form = backup.components[0]

            core_config['backup']['enabled'] = bkp_form.get_component('enabled').get_selected()
            core_config['backup']['mode'] = bkp_form.get_component('mode').get_selected()
            core_config['backup']['install'] = bkp_form.get_component('install').get_selected()
            core_config['backup']['uninstall'] = bkp_form.get_component('uninstall').get_selected()
            core_config['backup']['upgrade'] = bkp_form.get_component('upgrade').get_selected()
            core_config['backup']['downgrade'] = bkp_form.get_component('downgrade').get_selected()

        # tray
        tray_form = tray.components[0]
        core_config['updates']['check_interval'] = tray_form.get_component('updates_interval').get_int_value()

        def_icon_path = tray_form.get_component('def_icon').file_path
        core_config['ui']['tray']['default_icon'] = def_icon_path if def_icon_path else None

        up_icon_path = tray_form.get_component('up_icon').file_path
        core_config['ui']['tray']['updates_icon'] = up_icon_path if up_icon_path else None

        # ui
        ui_form = ui.components[0]

        core_config['download']['icons'] = ui_form.get_component('down_icons').get_selected()
        core_config['ui']['hdpi'] = ui_form.get_component('hdpi').get_selected()

        previous_autoscale = core_config['ui']['auto_scale']

        core_config['ui']['auto_scale'] = ui_form.get_component('auto_scale').get_selected()

        if previous_autoscale and not core_config['ui']['auto_scale']:
            self.logger.info("Deleting environment variable QT_AUTO_SCREEN_SCALE_FACTOR")
            del os.environ['QT_AUTO_SCREEN_SCALE_FACTOR']

        core_config['ui']['table']['max_displayed'] = ui_form.get_component('table_max').get_int_value()

        style = ui_form.get_component('style').get_selected()

        cur_style = core_config['ui']['style'] if core_config['ui']['style'] else QApplication.instance().style().objectName().lower()
        if style != cur_style:
            core_config['ui']['style'] = style

        # gems
        checked_gems = gems_panel.components[1].get_component('gems').get_selected_values()

        for man in self.managers:
            modname = man.__module__.split('.')[-2]
            enabled = modname in checked_gems
            man.set_enabled(enabled)

        core_config['gems'] = None if core_config['gems'] is None and len(checked_gems) == len(self.managers) else checked_gems

        try:
            config.save(core_config)
            return True, None
        except:
            return False, [traceback.format_exc()]

    def save_settings(self, component: TabGroupComponent) -> Tuple[bool, List[str]]:

        saved, warnings = True, []

        bkp = component.get_tab('core.bkp')
        success, errors = self._save_settings(general=component.get_tab('core.gen').content,
                                              advanced=component.get_tab('core.adv').content,
                                              tray=component.get_tab('core.tray').content,
                                              backup=bkp.content if bkp else None,
                                              ui=component.get_tab('core.ui').content,
                                              gems_panel=component.get_tab('core.types').content)

        if not success:
            saved = False

        if errors:
            warnings.extend(errors)

        for man in self.managers:
            if man:
                modname = man.__module__.split('.')[-2]
                tab = component.get_tab(modname)

                if not tab:
                    self.logger.warning("Tab for {} was not found".format(man.__class__.__name__))
                else:
                    res = man.save_settings(tab.content)

                    if res:
                        success, errors = res[0], res[1]

                        if not success:
                            saved = False

                        if errors:
                            warnings.extend(errors)

        return saved, warnings

    def _gen_backup_settings(self, core_config: dict, screen_width: int, screen_height: int) -> TabComponent:
        if timeshift.is_available():
            default_width = floor(0.22 * screen_width)

            enabled_opt = self._gen_bool_component(label=self.i18n['core.config.backup'],
                                                   tooltip=None,
                                                   value=bool(core_config['backup']['enabled']),
                                                   id_='enabled',
                                                   max_width=default_width)

            ops_opts = [(self.i18n['yes'].capitalize(), True, None),
                        (self.i18n['no'].capitalize(), False, None),
                        (self.i18n['ask'].capitalize(), None, None)]

            install_mode = self._gen_select(label=self.i18n['core.config.backup.install'],
                                            tip=None,
                                            value=core_config['backup']['install'],
                                            opts=ops_opts,
                                            max_width=default_width,
                                            id_='install')

            uninstall_mode = self._gen_select(label=self.i18n['core.config.backup.uninstall'],
                                              tip=None,
                                              value=core_config['backup']['uninstall'],
                                              opts=ops_opts,
                                              max_width=default_width,
                                              id_='uninstall')

            upgrade_mode = self._gen_select(label=self.i18n['core.config.backup.upgrade'],
                                            tip=None,
                                            value=core_config['backup']['upgrade'],
                                            opts=ops_opts,
                                            max_width=default_width,
                                            id_='upgrade')

            downgrade_mode = self._gen_select(label=self.i18n['core.config.backup.downgrade'],
                                              tip=None,
                                              value=core_config['backup']['downgrade'],
                                              opts=ops_opts,
                                              max_width=default_width,
                                              id_='downgrade')

            mode = self._gen_select(label=self.i18n['core.config.backup.mode'],
                                    tip=None,
                                    value=core_config['backup']['mode'],
                                    opts=[
                                        (self.i18n['core.config.backup.mode.incremental'], 'incremental',
                                         self.i18n['core.config.backup.mode.incremental.tip']),
                                        (self.i18n['core.config.backup.mode.only_one'], 'only_one',
                                         self.i18n['core.config.backup.mode.only_one.tip'])
                                    ],
                                    max_width=default_width,
                                    id_='mode')

            sub_comps = [FormComponent([enabled_opt, mode, install_mode, uninstall_mode, upgrade_mode, downgrade_mode], spaces=False)]
            return TabComponent(self.i18n['core.config.tab.backup'].capitalize(), PanelComponent(sub_comps), None, 'core.bkp')

    def _gen_select(self, label: str, tip: str, id_: str, opts: List[tuple], value: object, max_width: int, type_: SelectViewType = SelectViewType.RADIO):
        inp_opts = [InputOption(label=o[0].capitalize(), value=o[1], tooltip=o[2]) for o in opts]
        def_opt = [o for o in inp_opts if o.value == value]
        return SingleSelectComponent(label=label,
                                     tooltip=tip,
                                     options=inp_opts,
                                     default_option=def_opt[0] if def_opt else inp_opts[0],
                                     max_per_line=len(inp_opts),
                                     max_width=max_width,
                                     type_=type_,
                                     id_=id_)

