import datetime
import operator
import time
from functools import reduce
from typing import Tuple

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QTableWidget, QHeaderView, QPushButton, QToolBar, \
    QProgressBar, QApplication

from bauh import __app_name__
from bauh.api.abstract.context import ApplicationContext
from bauh.api.abstract.controller import SoftwareManager
from bauh.api.abstract.handler import TaskManager
from bauh.view.qt import root
from bauh.view.qt.components import new_spacer
from bauh.view.qt.qt_utils import centralize
from bauh.view.qt.thread import AnimateProgress
from bauh.view.util.translation import I18n


class Prepare(QThread, TaskManager):
    signal_register = pyqtSignal(str, str, object)
    signal_update = pyqtSignal(str, float, str)
    signal_finished = pyqtSignal(str)
    signal_started = pyqtSignal()
    signal_ask_password = pyqtSignal()

    def __init__(self, context: ApplicationContext, manager: SoftwareManager, i18n: I18n):
        super(Prepare, self).__init__()
        self.manager = manager
        self.i18n = i18n
        self.context = context
        self.waiting_password = False
        self.password_response = None

    def ask_password(self) -> Tuple[str, bool]:
        self.waiting_password = True
        self.signal_ask_password.emit()

        while self.waiting_password:
            time.sleep(0.1)  # waiting for user input

        return self.password_response

    def set_password_reply(self, password: str, valid: bool):
        self.password_response = password, valid
        self.waiting_password = False

    def run(self):
        root_pwd = None
        if self.manager.requires_root('prepare', None):
            root_pwd, ok = self.ask_password()

            if not ok:
                QCoreApplication.exit(1)

        self.signal_started.emit()
        self.manager.prepare(self, root_pwd, None)

    def update_progress(self, task_id: str, progress: float, substatus: str):
        self.signal_update.emit(task_id, progress, substatus)

    def register_task(self, id_: str, label: str, icon_path: str):
        self.signal_register.emit(id_, label, icon_path)

    def finish_task(self, task_id: str):
        self.signal_finished.emit(task_id)


class CheckFinished(QThread):
    signal_finished = pyqtSignal()

    def __init__(self):
        super(CheckFinished, self).__init__()
        self.total = None
        self.finished = None

    def run(self):
        while True:
            if self.total is not None and self.finished is not None:
                if self.total == self.finished:
                    break

            time.sleep(0.01)

        self.signal_finished.emit()

    def update(self, total: int, finished: int):
        if total is not None:
            self.total = total

        if finished is not None:
            self.finished = finished


class EnableSkip(QThread):

    signal_timeout = pyqtSignal()

    def run(self):
        ti = datetime.datetime.now()

        while True:
            if datetime.datetime.now() >= ti + datetime.timedelta(minutes=1.5):
                self.signal_timeout.emit()
                break

            time.sleep(0.1)


class PreparePanel(QWidget, TaskManager):

    signal_status = pyqtSignal(object, object)
    signal_password_response = pyqtSignal(str, bool)

    def __init__(self, context: ApplicationContext, manager: SoftwareManager, screen_size: QSize,  i18n: I18n, manage_window: QWidget):
        super(PreparePanel, self).__init__()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.i18n = i18n
        self.context = context
        self.manage_window = manage_window
        self.setWindowTitle('{} ({})'.format(self.i18n['prepare_panel.title.start'].capitalize(), __app_name__))
        self.setMinimumWidth(screen_size.width() * 0.5)
        self.setMinimumHeight(screen_size.height() * 0.35)
        self.setMaximumHeight(screen_size.height() * 0.95)
        self.setLayout(QVBoxLayout())
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        self.manager = manager
        self.tasks = {}
        self.ntasks = 0
        self.ftasks = 0
        self.self_close = False

        self.prepare_thread = Prepare(self.context, manager, self.i18n)
        self.prepare_thread.signal_register.connect(self.register_task)
        self.prepare_thread.signal_update.connect(self.update_progress)
        self.prepare_thread.signal_finished.connect(self.finish_task)
        self.prepare_thread.signal_started.connect(self.start)
        self.prepare_thread.signal_ask_password.connect(self.ask_root_password)
        self.signal_password_response.connect(self.prepare_thread.set_password_reply)

        self.check_thread = CheckFinished()
        self.signal_status.connect(self.check_thread.update)
        self.check_thread.signal_finished.connect(self.finish)

        self.skip_thread = EnableSkip()
        self.skip_thread.signal_timeout.connect(self._enable_skip_button)

        self.progress_thread = AnimateProgress()
        self.progress_thread.signal_change.connect(self._change_progress)

        self.label_top = QLabel()
        self.label_top.setText("{}...".format(self.i18n['prepare_panel.title.start'].capitalize()))
        self.label_top.setAlignment(Qt.AlignHCenter)
        self.label_top.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        self.layout().addWidget(self.label_top)
        self.layout().addWidget(QLabel())

        self.table = QTableWidget()
        self.table.setStyleSheet("QTableWidget { background-color: transparent; }")
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['' for _ in range(4)])
        self.layout().addWidget(self.table)

        toolbar = QToolBar()
        self.bt_close = QPushButton(self.i18n['close'].capitalize())
        self.bt_close.clicked.connect(self.close)
        self.bt_close.setVisible(False)
        self.ref_bt_close = toolbar.addWidget(self.bt_close)

        toolbar.addWidget(new_spacer())
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(10 if QApplication.instance().style().objectName().lower() == 'windows' else 4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.ref_progress_bar = toolbar.addWidget(self.progress_bar)
        toolbar.addWidget(new_spacer())

        self.bt_skip = QPushButton(self.i18n['prepare_panel.bt_skip.label'].capitalize())
        self.bt_skip.clicked.connect(self.finish)
        self.bt_skip.setEnabled(False)
        toolbar.addWidget(self.bt_skip)

        self.layout().addWidget(toolbar)

    def ask_root_password(self):
        root_pwd, ok = root.ask_root_password(self.context, self.i18n)
        self.signal_password_response.emit(root_pwd, ok)

    def _enable_skip_button(self):
        self.bt_skip.setEnabled(True)

    def _change_progress(self, value: int):
        self.progress_bar.setValue(value)

    def get_table_width(self) -> int:
        return reduce(operator.add, [self.table.columnWidth(i) for i in range(self.table.columnCount())])

    def _resize_columns(self):
        header_horizontal = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            header_horizontal.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.resize(self.get_table_width() * 1.05, self.sizeHint().height())

    def show(self):
        super(PreparePanel, self).show()
        self.prepare_thread.start()
        centralize(self)

    def start(self):
        self.ref_bt_close.setVisible(True)
        self.check_thread.start()
        self.skip_thread.start()

        self.ref_progress_bar.setVisible(True)
        self.progress_thread.start()

    def closeEvent(self, QCloseEvent):
        if not self.self_close:
            QCoreApplication.exit()

    def register_task(self, id_: str, label: str, icon_path: str):
        self.ntasks += 1
        self.table.setRowCount(self.ntasks)

        task_row = self.ntasks - 1

        lb_icon = QLabel()
        lb_icon.setContentsMargins(10, 0, 10, 0)
        lb_icon.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        if icon_path:
            lb_icon.setPixmap(QIcon(icon_path).pixmap(14, 14))

        self.table.setCellWidget(task_row, 0, lb_icon)

        lb_status = QLabel(label)
        lb_status.setMinimumWidth(50)
        lb_status.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        lb_status.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        self.table.setCellWidget(task_row, 1, lb_status)

        lb_sub = QLabel()
        lb_sub.setContentsMargins(10, 0, 10, 0)
        lb_sub.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        lb_sub.setMinimumWidth(50)
        self.table.setCellWidget(task_row, 2, lb_sub)

        lb_progress = QLabel('{0:.2f}'.format(0) + '%')
        lb_progress.setContentsMargins(10, 0, 10, 0)
        lb_progress.setStyleSheet("QLabel { color: blue; font-weight: bold; }")
        lb_progress.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        self.table.setCellWidget(task_row, 3, lb_progress)

        self.tasks[id_] = {'lb_status': lb_status,
                           'lb_prog': lb_progress,
                           'progress': 0,
                           'lb_sub': lb_sub,
                           'finished': False}

        self.signal_status.emit(self.ntasks, self.ftasks)

    def update_progress(self, task_id: str, progress: float, substatus: str):
        task = self.tasks[task_id]

        if progress != task['progress']:
            task['progress'] = progress
            task['lb_prog'].setText('{0:.2f}'.format(progress) + '%')

        if substatus:
            task['lb_sub'].setText('( {} )'.format(substatus))
        else:
            task['lb_sub'].setText('')

        self._resize_columns()

    def finish_task(self, task_id: str):
        task = self.tasks[task_id]
        task['lb_sub'].setText('')

        for key in ('lb_prog', 'lb_status'):
            task[key].setStyleSheet('QLabel { color: green; text-decoration: line-through; }')

        task['finished'] = True
        self._resize_columns()

        self.ftasks += 1
        self.signal_status.emit(self.ntasks, self.ftasks)

        if self.ntasks == self.ftasks:
            self.label_top.setText(self.i18n['ready'].capitalize())

    def finish(self):
        if self.isVisible():
            self.manage_window.refresh_packages()
            self.manage_window.show()
            self.self_close = True
            self.close()
