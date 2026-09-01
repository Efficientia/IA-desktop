from langchain_core.tools import Tool
def tool_placeholder(*args, **kwargs): return "Ferramenta de análise de dados executada"
TOOLS = [Tool(name="analise_dados", func=tool_placeholder, description="Ferramenta de analise de dados")]
