from dataclasses import dataclass, field
from email.message import EmailMessage
import smtplib


class EmailService:
    def send_password_reset(self, recipient: str, token: str) -> None:
        raise NotImplementedError


@dataclass
class FakeEmailService(EmailService):
    messages: list[tuple[str, str]] = field(default_factory=list)

    def send_password_reset(self, recipient: str, token: str) -> None:
        self.messages.append((recipient, token))


@dataclass(frozen=True, slots=True)
class SMTPEmailService(EmailService):
    host: str
    port: int
    sender: str
    username: str = ""
    password: str = ""
    use_tls: bool = True

    def send_password_reset(self, recipient: str, token: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Finance — recuperação de senha"
        message["From"] = self.sender
        message["To"] = recipient
        message.set_content(
            "Foi solicitada a recuperação de sua senha do Finance. "
            f"Use este token uma única vez, dentro do prazo configurado: {token}"
        )
        with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)
