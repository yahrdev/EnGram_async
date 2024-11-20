"""The models of the api tables"""

from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from sqlalchemy import Integer, String, Text, Index, Enum, ForeignKey, DateTime
from sqlalchemy.ext.asyncio import AsyncSession,  create_async_engine, async_sessionmaker
from schemas import Levels
from const import TxtData
from config import settings
from typing import AsyncGenerator
from handlers import global_error_handler_sync

#here we create engine and a session. Also we create a function 
#which will open and will close the session before and after the app working

@global_error_handler_sync
def init_db_engine_and_session():
    engine = create_async_engine(settings.DB_URL)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, async_session_maker


engine, async_session_maker = init_db_engine_and_session()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:

    """General function for db session generating and managing to be used in different parts of the project
    The session already has a context manager so it will be automatically opened before and closed after using"""

    async with async_session_maker() as session:
        yield session
        



Base = declarative_base()  #create a basic class for our models



class BaseModel(Base):
    """Abstract class for using in other models creation"""


    __abstract__ = True

    def to_dict(self):

        """The method for queries results unpacking"""

        try:
            created_dict = {c.name: getattr(self, c.name) for c in self.__table__.columns}
            return created_dict
        except:
            raise ValueError(TxtData.DictConvertError)



class Questions(BaseModel):

    """the main table with questions list. 
    datetime_shown is for reflecting the time when a question was shown to a user last time"""

    __tablename__ = 'questions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index= True, autoincrement=True)
    level: Mapped[Enum] = mapped_column(Enum(Levels), nullable=False)
    question: Mapped[Text] = mapped_column(String(400), nullable=False)
    correct_id: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[Text] = mapped_column(String(500))
    datetime_shown: Mapped[DateTime] = mapped_column(DateTime, default=None, nullable=True)

    def to_dict(self):
        d = super().to_dict()
        d["level"] = self.level.value  #because otherwise enum will not be JSON serializable
        return d


class Options(BaseModel):

    """the table with possible answers"""

    __tablename__ = 'options'

    question_id: Mapped[int] = mapped_column(Integer,  ForeignKey('questions.id'), primary_key=True)
    option_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    option_text: Mapped[Text] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        Index('ix_question_option', 'question_id', 'option_id', unique=True),
    )
