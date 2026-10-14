from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QTextBrowser, QVBoxLayout,
)

SUPPORT_WHATSAPP_DISPLAY = "(62) 9 8167-2265"
SUPPORT_WHATSAPP_NUMBER = "5562981672265"

TOPICS = {
    "Como usar o Finance": "O Finance centraliza as rotinas financeiras, de BOE, metas, cadastros e relatórios. Use a navegação lateral para acessar os módulos liberados para o seu perfil.",
    "Dashboard": "Apresenta os indicadores permitidos ao seu perfil. Utilize os filtros disponíveis para consultar o período desejado e Atualizar para recarregar os dados.",
    "Financeiro": "Permite consultar o fluxo financeiro. Perfis autorizados também podem incluir lançamentos e realizar as importações disponíveis.",
    "BOE": "Permite consultar os dados de BOE e, quando autorizado, executar as operações disponíveis no módulo.",
    "Orçado x Realizado": "Compara valores orçados e realizados conforme o período e os filtros disponíveis.",
    "Metas e Ranking": "O módulo Metas permite acompanhar metas e realizados. A área Ranking e Premiação apresenta a classificação calculada conforme os parâmetros do ano.",
    "Cadastros": "Reúne a Base Mestre de Entidades e o Catálogo do Fluxo de Caixa. As áreas e ações visíveis dependem das permissões do usuário.",
    "Relatórios": "Permite consultar relatórios e, para perfis autorizados, exportar os dados disponíveis.",
    "Administração": "Reúne Minha conta e, conforme o perfil, recursos administrativos, usuários, auditoria e parâmetros do Ranking.",
    "Recuperação de senha": "Na tela de entrada, use Esqueci minha senha. Se possuir sua chave pessoal, informe-a para redefinir a senha. Sem a chave, utilize Recuperação assistida e envie o código ao suporte pelo WhatsApp (62) 9 8167-2265.",
    "Perguntas Frequentes": "Se uma opção não estiver visível, ela pode não estar liberada para o seu perfil. Em caso de dúvida operacional ou necessidade de recuperação assistida, fale com o suporte.",
}


class HelpDialog(QDialog):
    # JA_TECH_FINANCE_HELP_BOOKMAKER_V2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Finance \u2014 Central de Ajuda")
        self.setModal(True)
        self.setMinimumSize(900, 560)
        self.resize(980, 620)

        self._build_ui()
        self._apply_styles()
        self._filter("")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        title = QLabel("Central de Ajuda")
        title.setObjectName("HelpTitle")

        subtitle = QLabel("Orienta\u00e7\u00f5es r\u00e1pidas e suporte para utiliza\u00e7\u00e3o do Finance.")
        subtitle.setObjectName("HelpSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar orienta\u00e7\u00e3o")
        self.search.setMinimumHeight(40)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        body = QHBoxLayout()
        body.setSpacing(16)

        nav = QFrame()
        nav.setObjectName("HelpNavigation")
        nav.setFixedWidth(290)

        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(16, 16, 16, 16)
        nav_layout.setSpacing(10)

        nav_title = QLabel("GUIA R\u00c1PIDO")
        nav_title.setObjectName("HelpSectionTitle")

        self.topics = QListWidget()
        self.topics.setObjectName("HelpArticleList")
        self.topics.setSpacing(8)
        self.topics.currentTextChanged.connect(self._show_topic)

        nav_layout.addWidget(nav_title)
        nav_layout.addWidget(self.topics, 1)

        panel = QFrame()
        panel.setObjectName("HelpContentPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 18, 20, 18)
        panel_layout.setSpacing(12)

        content_title = QLabel("ORIENTA\u00c7\u00c3O")
        content_title.setObjectName("HelpSectionTitle")

        self.text = QTextBrowser()
        self.text.setObjectName("HelpContent")

        panel_layout.addWidget(content_title)
        panel_layout.addWidget(self.text, 1)

        body.addWidget(nav)
        body.addWidget(panel, 1)
        root.addLayout(body, 1)

        support = QFrame()
        support.setObjectName("HelpSupport")

        support_layout = QHBoxLayout(support)
        support_layout.setContentsMargins(16, 12, 16, 12)

        support_text = QLabel("Suporte e diagn\u00f3stico \u2014 atendimento oficial J.A. Technology")
        support_text.setObjectName("HelpSupportText")

        self.whatsapp = QPushButton(
            "Falar com o suporte pelo WhatsApp"
        )
        self.whatsapp.setObjectName("HelpWhatsAppButton")
        self.whatsapp.clicked.connect(self._open_whatsapp)

        support_layout.addWidget(support_text)
        support_layout.addStretch()
        support_layout.addWidget(self.whatsapp)

        root.addWidget(support)

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #F4F6F8;
            }

            QLabel#HelpTitle {
                color: #003B71;
                font-size: 24px;
                font-weight: 700;
            }

            QLabel#HelpSubtitle {
                color: #64748B;
                font-size: 13px;
            }

            QLabel#HelpSectionTitle {
                color: #003B71;
                font-size: 13px;
                font-weight: 700;
            }

            QFrame#HelpNavigation,
            QFrame#HelpContentPanel,
            QFrame#HelpSupport {
                background-color: #FFFFFF;
                border: 1px solid #D9E0E7;
                border-radius: 8px;
            }

            QListWidget#HelpArticleList {
                background-color: transparent;
                border: none;
                outline: none;
            }

            QListWidget#HelpArticleList::item {
                background-color: #F4F6F8;
                color: #334155;
                border: 1px solid #D5DDE5;
                border-radius: 7px;
                padding: 12px 14px;
                margin: 2px 0;
            }

            QListWidget#HelpArticleList::item:hover {
                background-color: #E9EEF3;
                border-color: #AAB7C4;
            }

            QListWidget#HelpArticleList::item:selected {
                background-color: #E1E7EC;
                color: #003B71;
                border: 1px solid #AAB7C4;
            }

            QTextBrowser#HelpContent {
                border: none;
                background-color: #FFFFFF;
                color: #334155;
                padding: 6px;
            }

            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
                padding: 7px 10px;
            }

            QLineEdit:focus {
                border-color: #4C8FC0;
            }

            QLabel#HelpSupportText {
                color: #475569;
            }

            QPushButton#HelpWhatsAppButton {
                background-color: #EDF7F5;
                color: #176D66;
                border: 1px solid #B4D8D2;
                border-radius: 7px;
                padding: 7px 12px;
                font-weight: 600;
                min-height: 24px;
            }

            QPushButton#HelpWhatsAppButton:hover {
                background-color: #DDEFEA;
                border-color: #42978E;
            }

            QPushButton#HelpWhatsAppButton:pressed {
                background-color: #91C9C2;
            }
        """)

    def _filter(self, value: str) -> None:
        query = value.strip().casefold()
        current = self.topics.currentItem().text() if self.topics.currentItem() else ""
        self.topics.clear()
        for title, body in TOPICS.items():
            if not query or query in title.casefold() or query in body.casefold():
                self.topics.addItem(title)
        matches = self.topics.findItems(current, Qt.MatchFlag.MatchExactly)
        if matches:
            self.topics.setCurrentItem(matches[0])
        elif self.topics.count():
            self.topics.setCurrentRow(0)
        else:
            self.text.setPlainText("Nenhuma orientação encontrada para a busca informada.")

    def _show_topic(self, title: str) -> None:
        if title:
            self.text.setHtml(f"<h3>{title}</h3><p>{TOPICS[title]}</p>")

    def _open_whatsapp(self) -> None:
        message = "Olá. Preciso de ajuda com o Finance da J.A. Technology."
        encoded = bytes(QUrl.toPercentEncoding(message)).decode("ascii")
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{SUPPORT_WHATSAPP_NUMBER}?text={encoded}"))
