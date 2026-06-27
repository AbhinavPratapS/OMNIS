
from wakeword.wakeword import detect_wake_word
from modules.time_module import start_scheduler
from rich.console import Console
from rich.panel import Panel

console = Console()

def main():
    console.print(Panel.fit(
        "[bold cyan]OMNIX AI VOICE ASSISTANT[/bold cyan]\n"
        "[dim]Native PipeWire Engine | Local-First Rule Intent Parser | Gemini Fallback[/dim]",
        title="[bold green]System Active[/bold green]",
        border_style="cyan"
    ))
    
    start_scheduler()

    while True:
        detect_wake_word()

if __name__ == "__main__":
    main()

