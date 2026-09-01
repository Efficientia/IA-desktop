from langchain_core.tools import Tool
def tool_placeholder(*args, **kwargs): return "Ferramenta de planejamento executada"
TOOLS_AGENDA = [Tool(name="planejamento", func=tool_placeholder, description="Ferramenta de planejamento")]
