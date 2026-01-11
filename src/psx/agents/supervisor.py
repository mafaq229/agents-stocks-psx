"""Supervisor Agent for orchestrating multi-agent stock analysis.

Coordinates Data, Analyst, and Research agents to produce comprehensive analysis.
"""

import json
import logging
import re
from typing import Any, Optional

from psx.agents.llm import LLMClient, Tool
from psx.agents.schemas import (
    AnalysisState,
    AnalysisReport,
    DataAgentOutput,
    AnalystOutput,
    ResearchOutput,
)
from psx.agents.data_agent import DataAgent
from psx.agents.analyst_agent import AnalystAgent
from psx.agents.research_agent import ResearchAgent
from psx.core.config import get_config, LLMProvider


logger = logging.getLogger(__name__)


SUPERVISOR_SYSTEM_PROMPT = """You are a Supervisor Agent that orchestrates stock analysis.

You coordinate three specialized agents:
1. DataAgent - Retrieves all stock data including peer discovery
2. AnalystAgent - Performs financial analysis and valuation
3. ResearchAgent - Searches news, parses PDFs (qualitative research)

Your responsibilities:
1. Parse user queries to identify stocks to analyze
2. Decide which agents to call and in what order
3. Pass context between agents
4. Synthesize results into a final report

Workflow for "Analyze X":
1. Call DataAgent to get stock data (includes peer discovery and peer data)
2. Call ResearchAgent for news and PDF analysis
3. Call AnalystAgent with data and research context
4. Synthesize into final recommendation

Always respond with a JSON object specifying next action:
{
    "action": "call_agent" | "synthesize" | "done",
    "agent": "data" | "analyst" | "research",
    "task": "...",
    "symbols": ["..."],
    "reasoning": "..."
}

Or when ready to synthesize:
{
    "action": "synthesize",
    "reasoning": "..."
}"""


SYNTHESIS_PROMPT = """Given the collected data, research, and analysis, create a comprehensive investment report.

DATA:
{data_context}

RESEARCH:
{research_context}

ANALYSIS:
{analysis_context}

Generate a JSON response with these sections:
{{
    "business_overview": "2-3 sentences: what the company does, key products, competitive position",
    "industry_context": "1-2 sentences: sector trends, regulatory factors",
    "ownership_structure": {{"promoter": "X%", "institutional": "Y%", "public": "Z%"}},
    "management_notes": ["CEO name and any notable board decisions"],
    "financial_snapshot": {{
        "stock_price": "Rs. X",
        "market_cap": "Rs. X",
        "pe_ratio": "X",
        "revenue": "Rs. X",
        "profit": "Rs. X",
        "profit_margin": "X%",
        "eps": "Rs. X",
        "roe": "X%",
        "debt_to_equity": "X",
        "current_ratio": "X"
    }},
    "valuation_table": [
        {{"method": "P/E Based", "value": X, "inputs": "Sector PE × EPS"}},
        {{"method": "Graham", "value": Y, "inputs": "..."}},
        {{"method": "Book Value", "value": Z, "inputs": "..."}}
    ],
    "peer_comparison_table": [
        {{"symbol": "XXX", "price": X, "pe_ratio": X, "roe": X, "market_cap": X}}
    ],
    "relative_position": "How company compares to peers - e.g., cheapest in sector",
    "strengths": [
        {{"point": "Strong market position", "reasoning": "Why this matters for investment"}},
        {{"point": "...", "reasoning": "..."}}
    ],
    "risks": [
        {{"point": "High debt levels", "reasoning": "Impact on investment thesis"}},
        {{"point": "...", "reasoning": "..."}}
    ],
    "recent_developments": ["News item 1", "Announcement 2"],
    "reasoning": "3-4 sentence investment thesis connecting valuation, fundamentals, risks, and timing",
    "entry_price": X,
    "target_price": Y,
    "stop_loss": Z
}}

Important:
- Extract actual numbers from the data provided
- For ownership, use available data or note "Not available"
- Be specific with financial figures
- Reasoning should explain WHY the recommendation makes sense NOW"""


class SupervisorAgent:
    """Orchestrates multi-agent stock analysis."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        max_iterations: int = 5,
    ):
        """Initialize supervisor with sub-agents.

        Args:
            llm_provider: Override default LLM provider
            max_iterations: Maximum iterations for analysis
        """
        config = get_config()
        provider = llm_provider or config.llm.provider

        # Supervisor uses fast model for routing decisions
        self.llm = LLMClient(
            provider=provider,
            model=config.get_model_for_agent("supervisor"),
            temperature=0.0,
            max_tokens=4096,  # Supervisor just emits routing JSON, not large outputs
        )

        # Synthesis uses smart model for comprehensive report generation
        self.synthesis_llm = LLMClient(
            provider=provider,
            model=config.get_model_for_agent("synthesis"),
            temperature=0.0,
            max_tokens=8192,  # Large output for detailed synthesis
        )

        self.max_iterations = max_iterations

        # Initialize sub-agents with appropriate models
        self.data_agent = DataAgent(
            llm_provider=provider,
            llm_model=config.get_model_for_agent("data"),
        )
        self.analyst_agent = AnalystAgent(
            llm_provider=provider,
            llm_model=config.get_model_for_agent("analyst"),
        )
        self.research_agent = ResearchAgent(
            llm_provider=provider,
            llm_model=config.get_model_for_agent("research"),
        )

        logger.info(
            f"[Supervisor] Initialized with models: "
            f"supervisor={config.get_model_for_agent('supervisor')}, "
            f"synthesis={config.get_model_for_agent('synthesis')}, "
            f"data={config.get_model_for_agent('data')}, "
            f"analyst={config.get_model_for_agent('analyst')}, "
            f"research={config.get_model_for_agent('research')}"
        )

    def analyze(self, query: str) -> AnalysisReport:
        """Analyze stocks based on user query.

        Args:
            query: User query (e.g., "Analyze OGDC", "Should I buy PPL?")

        Returns:
            AnalysisReport with comprehensive analysis
        """
        logger.info(f"Supervisor starting analysis: {query}")

        # Initialize state
        state = AnalysisState(query=query)

        # Extract symbols from query
        state.symbols = self._extract_symbols(query)
        logger.info(f"[Supervisor] Extracted symbols: {state.symbols}")

        if not state.symbols:
            return AnalysisReport(
                query=query,
                symbols=[],
                summary="Could not identify any stock symbols in the query.",
                recommendation="HOLD",
                confidence=0.0,
            )

        # Run analysis loop
        while state.iteration < self.max_iterations:
            state.iteration += 1
            logger.debug(f"[Supervisor] === Iteration {state.iteration}/{self.max_iterations} ===")

            # Get next action from LLM
            next_action = self._plan_next_action(state)
            logger.debug(f"[Supervisor] Planned action: {json.dumps(next_action, default=str)[:500]}")

            if next_action.get("action") == "call_agent":
                agent_type = next_action.get("agent", "unknown")
                symbols = next_action.get("symbols", state.symbols)
                task = next_action.get("task", "")
                logger.info(f"[Supervisor] 📤 Delegating to {agent_type.upper()} agent for {symbols}")
                logger.debug(f"[Supervisor]    Task: {task[:200]}...")
                self._execute_agent_call(state, next_action)
            elif next_action.get("action") == "synthesize":
                logger.info("[Supervisor] 📊 Synthesizing final report")
                return self._create_report(state, next_action)
            elif next_action.get("action") == "done":
                logger.info("[Supervisor] ✅ Analysis complete")
                break
            else:
                logger.warning(f"[Supervisor] Unknown action: {next_action}")
                break

        # Max iterations - synthesize what we have
        logger.info("[Supervisor] Max iterations reached, synthesizing available data")
        return self._create_report(state, {"action": "synthesize"})

    def _extract_symbols(self, query: str) -> list[str]:
        """Extract stock symbols from query."""
        # Common PSX symbols pattern (3-6 uppercase letters)
        pattern = r'\b([A-Z]{3,6})\b'
        matches = re.findall(pattern, query.upper())

        # Filter out common words
        stop_words = {"THE", "AND", "FOR", "BUY", "SELL", "HOLD", "STOCK", "SHOULD"}
        symbols = [m for m in matches if m not in stop_words]

        return list(dict.fromkeys(symbols))  # Remove duplicates, preserve order

    def _plan_next_action(self, state: AnalysisState) -> dict[str, Any]:
        """Ask LLM to plan next action."""
        messages = [
            {
                "role": "user",
                "content": f"Query: {state.query}\n\n"
                f"Current state:\n{state.to_context_string()}\n\n"
                "What should we do next?",
            }
        ]
        # TODO: for first iteration, is there a better way? current: [{'role': 'user', 'content': 'Query: MARI\n\nCurrent state:\n=== Analysis State ===\nQuery: MARI\nSymbols: MARI\nIteration: 1/10\n\nWhat should we do next?'}]
        response = self.llm.chat(
            messages=messages,
            system=SUPERVISOR_SYSTEM_PROMPT,
        )

        # Parse response as JSON (usual workflow of the system)
        try:
            # Find JSON in response: searches of a substring that starts with { and ends with }
            json_match = re.search(r'\{[\s\S]*\}', response.content) # re.Match object (not str)
            if json_match:
                return json.loads(json_match.group()) # .group() returns the matched JSON
        except json.JSONDecodeError:
            pass

        # Default to synthesize if we have data
        if state.data:
            return {"action": "synthesize"}

        # Default to getting data for first symbol
        if state.symbols:
            return {
                "action": "call_agent",
                "agent": "data",
                "symbols": [state.symbols[0]],
                "task": f"Get data for {state.symbols[0]}",
            }

        return {"action": "done"}

    def _execute_agent_call(
        self, state: AnalysisState, action: dict[str, Any]
    ) -> None:
        """Execute an agent call and update state."""
        agent_type = action.get("agent", "")
        task = action.get("task", "")
        symbols = action.get("symbols", state.symbols)

        for symbol in symbols:
            try:
                if agent_type == "data":
                    logger.info(f"[Supervisor] 📥 DataAgent fetching data for {symbol}")
                    result = self.data_agent.run(task or f"Get data for {symbol}")
                    state.data[symbol] = result
                    logger.debug(f"[Supervisor] DataAgent returned data with keys: {list(vars(result).keys()) if hasattr(result, '__dict__') else 'N/A'}")

                elif agent_type == "research":
                    logger.info(f"[Supervisor] 📥 ResearchAgent researching {symbol}")
                    context = {}
                    company_name = symbol  # Default to symbol
                    if symbol in state.data:
                        data_output = state.data[symbol]
                        context["data"] = data_output
                        # Extract company name for better search
                        if hasattr(data_output, 'company') and data_output.company:
                            if hasattr(data_output.company, 'name') and data_output.company.name:
                                company_name = data_output.company.name
                            elif hasattr(data_output.company, 'description') and data_output.company.description:
                                # Use first sentence of description as company name context
                                desc = data_output.company.description
                                company_name = f"{symbol} ({desc[:100]}...)" if len(desc) > 100 else f"{symbol} ({desc})"

                        # Pass sector for news context
                        if hasattr(data_output, 'sector') and data_output.sector:
                            context["sector"] = data_output.sector

                    # TODO: add sector as well for general news. also see government regulations, market trends and economic factors affecting the sector
                    research_task = task or f"Research news and reports for {company_name} (PSX symbol: {symbol})"
                    result = self.research_agent.run(
                        research_task,
                        context=context,
                    )
                    state.research[symbol] = result
                    if hasattr(result, 'news_items'):
                        logger.debug(f"[Supervisor] ResearchAgent found {len(result.news_items)} news items")

                elif agent_type == "analyst":
                    logger.info(f"[Supervisor] 📥 AnalystAgent analyzing {symbol}")
                    context = {}
                    if symbol in state.data:
                        data_output = state.data[symbol]
                        context["data"] = data_output

                        # Include peer data for comparison
                        if hasattr(data_output, 'peer_data') and data_output.peer_data:
                            context["peer_data"] = [
                                p.to_dict() if hasattr(p, 'to_dict') else p
                                for p in data_output.peer_data
                            ]
                            logger.debug(f"[Supervisor] Passing {len(data_output.peer_data)} peers to AnalystAgent")

                        # Include sector averages for benchmarking
                        if hasattr(data_output, 'sector_averages') and data_output.sector_averages:
                            context["sector_averages"] = data_output.sector_averages
                            logger.debug("[Supervisor] Passing sector averages to AnalystAgent")

                    if symbol in state.research:
                        context["research"] = state.research[symbol]

                    # TODO: see if task needs improvement
                    result = self.analyst_agent.run(
                        task or f"Analyze {symbol} and compare with sector peers",
                        context=context,
                    )
                    state.analysis[symbol] = result
                    if hasattr(result, 'recommendation'):
                        logger.debug(f"[Supervisor] AnalystAgent recommendation: {result.recommendation}, confidence: {result.confidence}")

            except Exception as e:
                logger.error(f"[Supervisor] ❌ Agent call failed for {symbol}: {e}")
                state.errors.append(f"{agent_type} failed for {symbol}: {str(e)}")

    def _create_report(
        self, state: AnalysisState, synthesis: dict[str, Any]
    ) -> AnalysisReport:
        """Create final analysis report using LLM synthesis."""
        # Determine overall recommendation from AnalystAgent outputs
        recommendations = []
        confidences = []
        fair_value = None
        margin_of_safety = None

        for symbol, analysis in state.analysis.items():
            if isinstance(analysis, AnalystOutput):
                recommendations.append(analysis.recommendation)
                confidences.append(analysis.confidence)
                if analysis.fair_value:
                    fair_value = analysis.fair_value
                if analysis.margin_of_safety is not None:
                    margin_of_safety = analysis.margin_of_safety

        # Majority recommendation
        if recommendations:
            from collections import Counter
            recommendation = Counter(recommendations).most_common(1)[0][0]
            confidence = sum(confidences) / len(confidences) if confidences else 0.5
        else:
            recommendation = synthesis.get("recommendation", "HOLD")
            confidence = synthesis.get("confidence", 0.5)

        # Build context strings for LLM synthesis
        data_context = "\n\n".join(
            d.to_context_string() for d in state.data.values()
        ) if state.data else "No data collected."

        research_context = "\n\n".join(
            r.to_context_string() for r in state.research.values()
        ) if state.research else "No research conducted."

        analysis_context = "\n\n".join(
            a.to_context_string() for a in state.analysis.values()
        ) if state.analysis else "No analysis performed."

        # Call LLM to synthesize comprehensive report (uses smart model)
        logger.info("[Supervisor] Calling synthesis LLM for comprehensive report")
        try:
            synthesis_response = self.synthesis_llm.chat(
                messages=[{
                    "role": "user",
                    "content": SYNTHESIS_PROMPT.format(
                        data_context=data_context,
                        research_context=research_context,
                        analysis_context=analysis_context,
                    )
                }],
                system="You are a financial analyst creating investment reports. Respond only with valid JSON.",
            )

            # Parse synthesis JSON
            json_match = re.search(r'\{[\s\S]*\}', synthesis_response.content)
            if json_match:
                synth = json.loads(json_match.group())
            else:
                logger.warning("[Supervisor] Could not parse synthesis JSON, using defaults")
                synth = {}
        except Exception as e:
            logger.error(f"[Supervisor] LLM synthesis failed: {e}")
            synth = {}

        # Build peer comparison table from analyst output if not in synthesis
        peer_comparison_table = synth.get("peer_comparison_table", [])
        if not peer_comparison_table:
            for _, analysis in state.analysis.items():
                if isinstance(analysis, AnalystOutput) and analysis.peer_comparison:
                    for peer in analysis.peer_comparison:
                        peer_comparison_table.append(peer.to_dict())

        # Build valuation table from analyst output if not in synthesis
        valuation_table = synth.get("valuation_table", [])
        if not valuation_table:
            for _, analysis in state.analysis.items():
                if isinstance(analysis, AnalystOutput) and analysis.valuations:
                    for v in analysis.valuations:
                        valuation_table.append({
                            "method": v.method,
                            "value": v.value,
                            "inputs": v.notes or str(v.inputs),
                        })

        return AnalysisReport(
            query=state.query,
            symbols=state.symbols,
            recommendation=recommendation,
            confidence=confidence,
            data=state.data,
            research=state.research,
            analysis=state.analysis,
            # Section 1: Business Overview
            business_overview=synth.get("business_overview", ""),
            industry_context=synth.get("industry_context", ""),
            # Section 2: Ownership & Management
            ownership_structure=synth.get("ownership_structure", {}),
            management_notes=synth.get("management_notes", []),
            # Section 3: Financial Snapshot
            financial_snapshot=synth.get("financial_snapshot", {}),
            # Section 4: Valuation
            valuation_table=valuation_table,
            fair_value=fair_value,
            margin_of_safety=margin_of_safety,
            # Section 5: Peer Comparison
            peer_comparison_table=peer_comparison_table,
            relative_position=synth.get("relative_position", ""),
            # Section 6: Investment Thesis
            strengths=synth.get("strengths", []),
            risks=synth.get("risks", []),
            recent_developments=synth.get("recent_developments", []),
            # Section 7: Recommendation
            reasoning=synth.get("reasoning", ""),
            entry_price=synth.get("entry_price"),
            target_price=synth.get("target_price"),
            stop_loss=synth.get("stop_loss"),
        )


def analyze_stock(query: str, verbose: bool = False) -> AnalysisReport:
    """Convenience function to analyze a stock.

    Args:
        query: Analysis query
        verbose: Enable verbose logging

    Returns:
        AnalysisReport
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    supervisor = SupervisorAgent()
    return supervisor.analyze(query)
