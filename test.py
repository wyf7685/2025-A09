from dotenv import load_dotenv

load_dotenv()

from app.core.chain import get_llm

llm = get_llm()
print(llm.invoke("请简单介绍一下自己"))