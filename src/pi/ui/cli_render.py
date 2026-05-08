import asyncio
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from config import MAX_ENERGY_GAUGE, UI_REFRESH_RATE, GeneratorType
from logic.game_state import GameState


class CLIRenderer:
    def __init__(self, game_state: GameState):
        self.game_state = game_state

    def generate_layout(self) -> Layout:
        session = self.game_state.current_session

        # 1. Progress Bars Layout
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )

        if session:
            for gen_type in GeneratorType:
                energy = session.energy_levels.get(gen_type, 0.0)
                progress.add_task(
                    f"[cyan]{gen_type.value}", total=MAX_ENERGY_GAUGE, completed=energy
                )

            total_energy = min(session.total_energy, MAX_ENERGY_GAUGE)
            progress.add_task(
                "[bold green]TOTAL POWER",
                total=MAX_ENERGY_GAUGE,
                completed=total_energy,
            )

        time_display = f"Time: {self.game_state.get_elapsed_time():.2f}s"
        status_panel = Panel(
            progress, title=f"⚡ CleanBoost Energy Dashboard | {time_display}"
        )

        # 2. Rankings Layout
        table = Table(title="Top Students")
        table.add_column("Rank", style="cyan", no_wrap=True)
        table.add_column("Student", style="magenta")
        table.add_column("Time (s)", justify="right", style="green")

        for i, rank in enumerate(self.game_state.rankings[:5], 1):
            table.add_row(str(i), rank.player_name, f"{rank.time_taken:.2f}")

        ranking_panel = Panel(table, title="🏆 Leaderboard")

        # Combine
        layout = Layout()
        layout.split_column(
            Layout(status_panel, name="upper", ratio=2),
            Layout(ranking_panel, name="lower", ratio=1),
        )
        return layout

    async def render_loop(self):
        with Live(
            self.generate_layout(), refresh_per_second=int(1 / UI_REFRESH_RATE)
        ) as live:
            while True:
                live.update(self.generate_layout())
                await asyncio.sleep(UI_REFRESH_RATE)
