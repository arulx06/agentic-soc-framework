"""Memory poisoning simulation placeholder."""


def inject_fake_memory(memory, fake_value):
    """Append a poisoned memory entry for experimentation."""
    memory.append(fake_value)
    return memory
