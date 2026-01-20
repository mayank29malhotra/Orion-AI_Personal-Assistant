import gradio as gr
from orion import Orion


async def setup():
    try:
        orion = Orion()
        await orion.setup()
        return orion
    except Exception as e:
        print(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def process_message(orion, message, success_criteria, history):
    if orion is None:
        return [[message, "Error: Orion failed to initialize. Please check your API keys and network connection."]], None
    try:
        results = await orion.run_superstep(message, success_criteria, history)
        return results, orion
    except Exception as e:
        print(f"Process message failed: {e}")
        import traceback
        traceback.print_exc()
        return [[message, f"Error: {str(e)}"]], orion


async def reset():
    new_orion = Orion()
    await new_orion.setup()
    return "", "", None, new_orion


def free_resources(orion):
    print("Cleaning up")
    try:
        if orion:
            orion.cleanup()
    except Exception as e:
        print(f"Exception during cleanup: {e}")


with gr.Blocks(title="Orion") as ui:
    gr.Markdown("## Orion Personal Co-Worker")
    orion = gr.State(delete_callback=free_resources)

    with gr.Row():
        chatbot = gr.Chatbot(label="Orion", height=300)
    with gr.Group():
        with gr.Row():
            message = gr.Textbox(show_label=False, placeholder="Your request to the Orion")
        with gr.Row():
            success_criteria = gr.Textbox(
                show_label=False, placeholder="What are your success critiera?"
            )
    with gr.Row():
        reset_button = gr.Button("Reset", variant="stop")
        go_button = gr.Button("Go!", variant="primary")

    ui.load(setup, [], [orion])
    message.submit(
        process_message, [orion, message, success_criteria, chatbot], [chatbot, orion]
    )
    success_criteria.submit(
        process_message, [orion, message, success_criteria, chatbot], [chatbot, orion]
    )
    go_button.click(
        process_message, [orion, message, success_criteria, chatbot], [chatbot, orion]
    )
    reset_button.click(reset, [], [message, success_criteria, chatbot, orion])


ui.launch(inbrowser=True, theme=gr.themes.Default(primary_hue="emerald"))
