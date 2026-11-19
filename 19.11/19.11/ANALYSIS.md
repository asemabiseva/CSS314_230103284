Question 1. MESI Protocol State Transitions

With stride = 1, both threads update different elements in the same 64-byte cache line. When Core 0 writes to buffer[0], it gets exclusive ownership and the line becomes Modified. When Core 1 tries to write buffer[1], it sends an RFO request. Core 0's copy becomes Invalid, and Core 1 gets ownership of the line. If Core 0 writes again, the same process happens in reverse. This creates constant cache-line transfers between cores. Core 1's store waits for ownership, which stalls its store buffer and slows execution.

Question 2. Quantitative Slowdown and Coherency Overhead

My measured results were:

stride = 1: 2,376,000 ns, or 0.0099 ns per update.
stride = 4: 1,856,700 ns, or 0.007736 ns per update.
stride = 8: 3,815,400 ns, or 0.015898 ns per update.
stride = 16: 6,000,100 ns, or 0.025000 ns per update.

Register-privatized: 52,344,000 ns, or 0.2181 ns per update.

The slowdown factor of stride 1 relative to stride 8 is 0.623x. This means stride 1 was actually faster in my experiment, instead of being slower. The results did not show the expected false-sharing overhead.

Question 3. L2 Spatial Prefetcher and 128-Byte Pairing

Stride 8 took 3,815,400 ns, while stride 16 took 6,000,100 ns. Stride 16 was about 1.57 times slower.

Some CPUs use adjacent-cache-line prefetching, where two neighboring 64-byte cache lines are fetched together as a 128-byte sector. Because of this, even 64-byte padding can sometimes cause extra cache traffic. Stride 16 separates the counters by 128 bytes, which can reduce this interference. However, my results show that stride 16 was slower, so this benefit was not visible in my experiment.

Question 4. Compiler Register Promotion vs. Memory Stores

An optimizing compiler may move a variable into a CPU register to avoid accessing memory repeatedly. However, in my kernel, every iteration reads the current value from buffer[slot] and writes the updated value back. This dependency makes it harder to replace the memory operations with one final register write. My LLVM inspection showed 4 load i64 instructions and 1 store i64 instruction. This confirms that native memory operations were generated, although the LLVM output alone does not prove that every iteration produces a separate hardware store.

Question 5. CPython GIL Masking vs. nogil=True

In standard Python threads, the GIL allows only one thread to execute Python bytecode at a time. Therefore, threads do not perform simultaneous counter updates on different CPU cores, and hardware false sharing is mostly hidden. Adding more threads can make the program slower because they compete for the GIL and spend time switching between threads.

With Numba's nogil=True, the native code can execute on multiple CPU cores at the same time. This allows real cache-coherency traffic and false sharing to occur.