import threading


def factorial(n):
    """Calculate factorial. BUG: Returns 0 for n=0 instead of 1."""
    if n <= 0:
        result = 0
    else:
        result = 1
        for i in range(2, n + 1):
            result *= i
    return result


def compute_parallel(numbers, num_threads=2):
    """
    Compute factorials in parallel using threads.

    Args:
        numbers: List of numbers to compute factorials for
        num_threads: Number of threads to use

    Returns:
        Dictionary mapping each number to its factorial
    """
    results = {}
    lock = threading.Lock()

    def worker(nums):
        for n in nums:
            fact = factorial(n)
            with lock:
                results[n] = fact

    chunk_size = len(numbers) // num_threads
    threads = []

    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size if i < num_threads - 1 else len(numbers)
        t = threading.Thread(target=worker, args=(numbers[start:end],))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return [results[n] for n in numbers]
