# [00]现代C++实践导读

# 现代 C++ 实践导读

时间：2026/05/08

这组笔记按“对象语义 -> 内存与所有权 -> 并发 -> 设计模式 -> 网络与协程 -> 常用工具 -> 泛型与编译期 -> 工程实践”的顺序整理。  
不建议按最早写作顺序读，建议优先按下面的编号顺序走。

---

## 1. 推荐阅读顺序

1. 对象生命周期、特殊成员函数与移动语义
2. 智能指针与所有权
3. allocator、自定义内存分配与 pmr
4. 生产者-消费者模式与阻塞队列
5. 线程同步消息队列与线程池
6. 工厂模式、多态与接口设计
7. 游戏常见设计模式
8. 对象布局、栈堆与未定义行为
9. 网络服务基础：TCP 粘包、线程模型与 HTTP(S)
10. C++20 协程入门与实践
11. 现代 C++ 常用工具类型
12. ranges 与 views
13. 错误处理与 `expected`、异常设计
14. 内存泄漏检测与管理
15. STL 容器、迭代器与算法实践
16. 编译模型、链接与 CMake 入门
17. 测试、调试与 Sanitizer 工具链
18. `const` 正确性、API 设计与现代属性
19. `constexpr`、`consteval` 与编译期计算实践
20. C++20 concepts 与泛型接口约束
21. 常用标准库组件：`format`、`chrono`、`filesystem` 与 `source_location`
22. 依赖管理与包管理：FetchContent、vcpkg、Conan

---

## 2. 这次整理做了什么

这套笔记经历了两轮整理：

1. 把错名、重复和草稿笔记重构成清晰主题
2. 把空白或过短内容补成可复习版本
3. 新增一篇缺失但非常常用的工具类型笔记
4. 补上了 `ranges/views`、错误处理设计，以及内存泄漏检测与管理这三块现代 C++ 高频主题
5. 补上了 STL 容器算法、编译链接/CMake、测试调试/Sanitizer 这三块工程实践基础
6. 补齐 API 设计、编译期计算、concepts、常用标准库组件、依赖管理这五块后续缺口，并尽量配了可直接复习的代码示例

---

## 3. 如果时间有限

优先看这 10 篇：

1. 生命周期、特殊成员函数与移动语义
2. 智能指针与所有权
3. STL 容器、迭代器与算法实践
4. 现代 C++ 常用工具类型
5. 错误处理与 `expected`、异常设计
6. `const` 正确性、API 设计与现代属性
7. `constexpr`、`consteval` 与编译期计算实践
8. C++20 concepts 与泛型接口约束
9. 编译模型、链接与 CMake 入门
10. 测试、调试与 Sanitizer 工具链

这几篇最直接影响现代 C++ 的工程写法。之后再看线程池、协程、ranges、网络和包管理。

---

## 4. 后续还可以补的主题

这次已经补齐了 API 设计、编译期计算、concepts、常用标准库组件和依赖管理。  
如果继续扩展，比较值得补的是：

1. 模块化与 C++20 modules 实践
2. 完美转发、引用折叠与泛型工厂
3. 类型擦除：`std::function`、自定义 type erasure 与多态替代
4. ABI 稳定性、PImpl 与动态库接口设计
5. 性能基准测试：Google Benchmark、profiling 与性能回归
6. 日志、配置、序列化等常见工程基础设施设计

---

## 5. 按实例复习的路线

如果想边看边练，可以优先按这些例子复习：

1. 生命周期实例：手写资源类、Rule of Five、返回值优化
2. 所有权实例：`unique_ptr/shared_ptr/weak_ptr`、自定义 deleter
3. 并发实例：阻塞队列、线程池、停止协议、任务返回值
4. 设计模式实例：注册表工厂、对象池、状态模式、命令模式
5. 网络实例：长度前缀拆包器、I/O 线程 + 业务线程池分层
6. 协程实例：最小 `generator`，理解 `co_yield` 和协程帧生命周期
7. 泛型实例：`concepts` 约束 range、策略对象接口、静态多态
8. 工程实例：CMake target、Sanitizer、FetchContent/vcpkg/Conan 依赖接入

---

# [01]对象生命周期、特殊成员函数与移动语义

# 对象生命周期、特殊成员函数与移动语义

时间：2026/04/09

> 关键词：生命周期、RAII、拷贝构造、拷贝赋值、移动构造、移动赋值、Rule of Zero/Five、`std::move`  
> 核心目标：搞清楚一个对象从创建到销毁会经历什么，以及类该如何正确管理资源。

---

## 1. 对象生命周期是什么

一个对象通常会经历：

1. 构造
2. 使用
3. 析构

最重要的实践原则是：

* 对象一旦构造完成，就应该处于“可用且满足类不变量”的状态
* 对象一旦析构完成，就不该再被访问

局部对象在离开作用域时析构：

```cpp
void f() {
    std::string s = "hello";
} // 这里自动析构
```

动态对象则由拥有者负责释放：

```cpp
auto p = std::make_unique<int>(42);
```

---

## 2. RAII 是生命周期管理的核心

RAII 的意思是：

* 构造时获取资源
* 析构时释放资源

典型资源包括：

* 动态内存
* 文件句柄
* socket
* 锁
* 线程句柄

RAII 的价值不是“语法优雅”，而是：

* 不容易忘记释放
* 异常发生时也能自动清理

---

## 3. 六个特殊成员函数

一个类最重要的 6 个函数是：

1. 默认构造函数
2. 析构函数
3. 拷贝构造函数
4. 拷贝赋值运算符
5. 移动构造函数
6. 移动赋值运算符

它们决定了对象如何：

* 创建
* 复制
* 转移资源
* 销毁

---

## 4. 拷贝构造 vs 拷贝赋值

### 4.1 拷贝构造

用一个对象去初始化另一个“新对象”：

```cpp
T b(a);
T c = a;
```

### 4.2 拷贝赋值

把一个已经存在的对象覆盖成另一个对象的状态：

```cpp
T b;
b = a;
```

核心差异：

* 拷贝构造是“从无到有”
* 拷贝赋值是“已有对象被覆盖”

后者通常还要考虑：

* 旧资源释放
* 自赋值
* 异常安全

---

## 5. 为什么移动语义很重要

如果一个类持有资源，单纯拷贝代价可能很大。

例如：

* 动态数组
* 大字符串
* 文件句柄包装对象

移动语义的核心思想是：

* 不复制资源内容
* 直接转移所有权或资源句柄

这就需要：

* 移动构造
* 移动赋值

---

## 6. `std::move` 到底在做什么

`std::move` 本身不移动资源。  
它只是把一个表达式转换成右值形式，让后续重载决议优先匹配移动版本。

```cpp
std::string s = "hello";
std::string t = std::move(s);
```

真正移动的是：

* `std::string` 的移动构造函数

不是 `std::move` 本身。

---

## 7. 一个最小资源类示例

```cpp
#include <algorithm>
#include <cstddef>

class Buffer {
public:
    Buffer() = default;

    explicit Buffer(std::size_t n)
        : size_(n), data_(n ? new int[n] : nullptr) {}

    ~Buffer() {
        delete[] data_;
    }

    Buffer(const Buffer& other)
        : size_(other.size_), data_(other.size_ ? new int[other.size_] : nullptr) {
        std::copy(other.data_, other.data_ + size_, data_);
    }

    Buffer& operator=(const Buffer& other) {
        if (this == &other) return *this;
        Buffer tmp(other);
        swap(tmp);
        return *this;
    }

    Buffer(Buffer&& other) noexcept
        : size_(other.size_), data_(other.data_) {
        other.size_ = 0;
        other.data_ = nullptr;
    }

    Buffer& operator=(Buffer&& other) noexcept {
        if (this == &other) return *this;
        delete[] data_;
        size_ = other.size_;
        data_ = other.data_;
        other.size_ = 0;
        other.data_ = nullptr;
        return *this;
    }

    void swap(Buffer& other) noexcept {
        std::swap(size_, other.size_);
        std::swap(data_, other.data_);
    }

private:
    std::size_t size_ = 0;
    int* data_ = nullptr;
};
```

这个例子体现了：

* 深拷贝
* 资源转移
* 移动后源对象置空

---

## 8. Rule of Three / Five / Zero

### 8.1 Rule of Three

如果类手写了下面之一，通常就要认真考虑另外两个：

* 析构
* 拷贝构造
* 拷贝赋值

因为这通常意味着类在管理资源。

### 8.2 Rule of Five

C++11 以后再加上：

* 移动构造
* 移动赋值

如果类显式管理资源，通常要一起考虑这五个。

### 8.3 Rule of Zero

现代 C++ 更推荐：

* 尽量不要自己手写资源管理
* 把资源交给现成 RAII 类型

例如：

* `std::vector`
* `std::string`
* `std::unique_ptr`

这样很多特殊成员函数甚至可以完全默认生成。

---

## 9. 默认生成和 `= default` / `= delete`

### 9.1 `= default`

显式告诉编译器：

* 用默认生成版本

```cpp
MyType() = default;
```

### 9.2 `= delete`

显式禁止某种操作：

```cpp
MyType(const MyType&) = delete;
MyType& operator=(const MyType&) = delete;
```

这在：

* 独占资源类型
* 锁对象
* 文件句柄包装类

里很常见。

---

## 10. 拷贝省略与返回值优化

现代 C++ 里：

```cpp
Buffer make_buffer() {
    Buffer b(1024);
    return b;
}
```

很多情况下不会真的发生拷贝，甚至连移动都可能被省掉。  
这就是：

* RVO
* NRVO
* guaranteed copy elision

所以写代码时不要过度手工干预，先让编译器优化。

---

## 11. 常见坑

### 11.1 移动后还把源对象当原值使用

移动后的对象通常只保证：

* 仍然有效
* 可以析构或重新赋值

但不保证保留原内容。

### 11.2 手写资源类却只写析构，不写拷贝/移动

这很容易造成：

* 双重释放
* 浅拷贝问题

### 11.3 拷贝赋值没处理自赋值和异常安全

尤其是手动 `delete` 再 `new` 的写法，容易把对象弄到半残状态。

### 11.4 本来可以 Rule of Zero，却硬写五个函数

不必要的手写资源管理会增加 bug 面积。

---

## 12. 一页总结

这篇最重要的是记住三件事：

1. 生命周期就是“构造到析构”的可控过程
2. 管资源的类必须认真处理拷贝和移动
3. 最好的实践通常不是手写五件套，而是尽量 Rule of Zero

如果只记一个工程结论：

> 能把资源交给现成 RAII 类型，就不要自己手写裸资源生命周期。

---

## 13. 建议继续补充的相关主题

1. 智能指针与所有权
2. 完美转发与引用折叠
3. 异常安全保证
4. `noexcept move` 与容器优化

---

# [02]智能指针与所有权

# 智能指针与所有权

时间：2026/04/09

> 关键词：所有权、观察者、`unique_ptr`、`shared_ptr`、`weak_ptr`、自定义删除器  
> 核心目标：把“谁负责释放资源”这件事表达清楚，而不是靠约定和记忆。

---

## 1. 为什么现代 C++ 强调所有权

裸指针只能表达：

* “这里有个地址”

但它不能天然表达：

* 谁拥有这个对象
* 谁负责释放
* 是否允许共享

现代 C++ 实践里，第一件要说清的就是所有权。

---

## 2. 三种常见关系

### 2.1 拥有（owning）

对象负责管理资源生命周期。

### 2.2 观察（non-owning）

对象只访问资源，不负责释放。

### 2.3 共享拥有（shared owning）

多个对象共同延长同一资源生命周期。

---

## 3. `unique_ptr`：默认首选

```cpp
#include <memory>

auto p = std::make_unique<int>(42);
```

特点：

* 独占所有权
* 不可拷贝
* 可移动
* 开销低

经验上：

* 只要不是明确需要共享，优先用 `unique_ptr`

---

## 4. `shared_ptr`：共享拥有

```cpp
auto p1 = std::make_shared<std::string>("hello");
auto p2 = p1;
```

特点：

* 引用计数
* 多个拥有者
* 生命周期更灵活

代价：

* 控制块
* 原子计数开销
* 更复杂的所有权关系

所以不要把它当默认选项。

---

## 5. `weak_ptr`：打破循环

`weak_ptr` 不拥有对象，只是观察。

```cpp
std::weak_ptr<Foo> weak = shared;
if (auto sp = weak.lock()) {
    // 对象还活着
}
```

它最重要的作用是：

* 避免两个 `shared_ptr` 互相引用导致循环泄漏

---

## 6. 原则：拥有和观察要分开

推荐的接口风格通常是：

```cpp
void take(std::unique_ptr<Foo> p); // 接管所有权
void use(Foo& x);                  // 一定存在，只观察
void maybe(Foo* p);                // 可为空观察
void share(std::shared_ptr<Foo> p);// 共享拥有
```

这比“什么都传裸指针”更清楚。

---

## 7. 自定义删除器

有些资源不是 `delete` 释放，例如：

* `FILE*` 要 `fclose`
* `malloc` 对应 `free`

可以这样包装：

```cpp
#include <cstdio>
#include <memory>

using FilePtr = std::unique_ptr<FILE, int(*)(FILE*)>;

FilePtr open_file(const char* path) {
    return FilePtr(std::fopen(path, "r"), std::fclose);
}
```

---

## 8. 常见误区

### 8.1 裸指针默认表示拥有

不推荐。  
裸指针更适合表达观察关系。

### 8.2 到处用 `shared_ptr`

这会让生命周期图变得混乱，还会带来额外开销。

### 8.3 从 `unique_ptr` 的 `get()` 拿到裸指针后乱删

`get()` 只是观察，不转移所有权。

---

## 9. 一页总结

最值得记住的顺序是：

1. 默认值语义
2. 必须动态分配时优先 `unique_ptr`
3. 确实共享拥有时才用 `shared_ptr`
4. 观察关系用引用、裸指针或 `weak_ptr`

如果只记一句：

> 智能指针不是为了“更高级”，而是为了把所有权表达清楚。

---

# [03]allocator、自定义内存分配与pmr入门

# allocator、自定义内存分配与 pmr 入门

时间：2026/04/09

> 关键词：`std::allocator`、`allocator_traits`、分配与构造分离、状态型分配器、`std::pmr`  
> 核心目标：理解 STL 容器如何管理内存，以及什么时候值得定制分配器。

---

## 1. 为什么 allocator 存在

容器不仅要“放元素”，还要处理：

* 申请原始内存
* 在内存上构造对象
* 销毁对象
* 释放内存

标准库把这层职责抽象成 allocator。

---

## 2. `std::allocator` 的核心职责

可以粗略理解成四步：

1. `allocate(n)`：分配能容纳 `n` 个对象的原始内存
2. `construct(...)`：在指定位置构造对象
3. `destroy(...)`：调用析构
4. `deallocate(...)`：释放内存

现代实现中更常通过：

* `std::allocator_traits`

来统一调度这些接口。

---

## 3. 为什么“分配”和“构造”是两件事

因为拿到一块内存，不等于对象已经存在。

```cpp
T* p = alloc.allocate(4); // 只有内存
std::construct_at(p, value); // 这里对象才真正构造
```

这也是容器能高效管理未初始化存储区的基础。

---

## 4. 一个最小自定义分配器骨架

```cpp
#include <memory>

template <class T>
struct MyAllocator {
    using value_type = T;

    MyAllocator() = default;

    template <class U>
    MyAllocator(const MyAllocator<U>&) {}

    T* allocate(std::size_t n) {
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }

    void deallocate(T* p, std::size_t) {
        ::operator delete(p);
    }
};
```

配合容器使用：

```cpp
std::vector<int, MyAllocator<int>> v;
```

---

## 5. 什么时候值得自定义 allocator

不是所有项目都需要。

更常见的适用场景：

* 频繁小对象分配
* 想用内存池减少碎片
* 想把对象放到特定区域
* 需要统计分配行为
* 游戏/服务端有帧级或 arena 分配需求

如果只是普通业务代码，标准分配器通常已经够用。

---

## 6. 状态型分配器

有些分配器不仅有类型，还有内部状态，例如：

* 指向某个内存池
* 指向某个 arena

这类分配器要特别注意：

* 拷贝行为
* 容器复制/移动时状态如何传播

这也是 `allocator_traits` 很重要的原因之一。

---

## 7. `std::pmr`：现代 C++ 更实用的内存资源抽象

C++17 提供了 `std::pmr`：

* polymorphic memory resource

它把“分配策略”从模板参数层搬到了运行时资源对象层。

最常见组件：

* `std::pmr::memory_resource`
* `std::pmr::polymorphic_allocator`
* `std::pmr::vector`
* `std::pmr::monotonic_buffer_resource`

这通常比手写 allocator 模板更实用。

---

## 8. `monotonic_buffer_resource` 的直觉

这种资源很适合：

* 批量分配
* 很少单独释放
* 整体回收

例如一次请求、一次帧更新、一次解析过程。

好处：

* 分配快
* 局部性好

代价：

* 单个对象通常不能灵活归还给池

---

## 9. 和容器性能的关系

allocator 影响的通常不是接口语义，而是：

* 分配次数
* 分配成本
* 碎片
* 局部性

但要注意：

* allocator 优化通常排在算法和数据布局之后
* 不要在没有证据前，把 allocator 当成首要瓶颈

---

## 10. 常见误区

### 10.1 把 allocator 当成“所有性能问题的解药”

很多性能问题其实更可能出在：

* 数据布局
* 扩容策略
* 锁争用
* 随机访问

### 10.2 只会写 `allocate/deallocate`，却不理解对象构造时机

allocator 真正重要的是：

* 内存和对象是分开的

### 10.3 在没有统一资源模型时滥用自定义 allocator

结果容易让代码复杂度大幅上升。

---

## 11. 参考实例：用 pmr 做一次请求内存池

假设一次请求里要临时创建很多字符串和数组，请求结束后统一释放。  
这时 `monotonic_buffer_resource` 很适合。

```cpp
#include <array>
#include <cstddef>
#include <iostream>
#include <memory_resource>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

struct RequestData {
    std::pmr::vector<std::pmr::string> headers;

    explicit RequestData(std::pmr::memory_resource* mr)
        : headers(mr) {}

    void add_header(std::string_view key, std::string_view value) {
        std::pmr::string line{headers.get_allocator().resource()};
        line.append(key);
        line.append(": ");
        line.append(value);
        headers.push_back(std::move(line));
    }
};

void handle_request() {
    std::array<std::byte, 4096> buffer{};
    std::pmr::monotonic_buffer_resource arena{
        buffer.data(),
        buffer.size()
    };

    RequestData req{&arena};
    req.add_header("Host", "example.com");
    req.add_header("User-Agent", "demo-client");

    for (const auto& h : req.headers) {
        std::cout << h << "\n";
    }

    // handle_request 返回时，arena 整体释放本次请求的临时内存。
}
```

这种模式适合：

* 请求级临时对象
* 一帧游戏逻辑里的临时容器
* 解析器中短生命周期 token

不适合：

* 单个对象需要频繁独立释放
* 容器或字符串要活得比 arena 更久

---

## 12. 一页总结

allocator 这篇最值得记住的是：

1. 容器管理的是“原始内存 + 对象构造/销毁”
2. allocator 负责内存来源
3. `allocator_traits` 是现代实现的核心适配层
4. 真正工程里，`std::pmr` 往往比手写 allocator 更实用

如果只记一句：

> allocator 优化通常是进阶优化，前提是你已经把算法、数据布局和容器选择做对了。

---

# [04]生产者-消费者模式与阻塞队列

# 生产者-消费者模式与阻塞队列

时间：2026/04/09

> 关键词：`mutex`、`condition_variable`、阻塞队列、bounded queue、shutdown、spurious wakeup  
> 核心目标：写出一个正确、可复用的生产者-消费者队列，而不是“能跑但容易死锁或卡住”的版本。

---

## 1. 这个模式在解决什么问题

生产者-消费者模式适用于：

* 生产方产生任务或消息
* 消费方异步处理
* 双方速度不一致

典型场景：

* 日志队列
* 任务队列
* 网络消息分发
* 线程池任务提交

它的核心不只是“一个队列”，而是三件事：

* 互斥
* 条件通知
* 生命周期关闭

---

## 2. 最小阻塞队列骨架

```cpp
#include <condition_variable>
#include <mutex>
#include <queue>

template <class T>
class BlockingQueue {
public:
    void push(T value) {
        {
            std::lock_guard<std::mutex> lk(mutex_);
            queue_.push(std::move(value));
        }
        cv_.notify_one();
    }

    T pop() {
        std::unique_lock<std::mutex> lk(mutex_);
        cv_.wait(lk, [&] { return !queue_.empty(); });
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }

private:
    std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<T> queue_;
};
```

---

## 3. 为什么一定要用谓词版 `wait`

错误直觉是：

```cpp
cv.wait(lock);
```

然后醒来就认为一定有数据。  
这是不安全的，因为存在：

* 虚假唤醒
* 多个线程竞争同一个条件

正确写法：

```cpp
cv.wait(lock, [&] { return !queue_.empty(); });
```

也就是：

* 醒来后重新检查条件

---

## 4. bounded queue：为什么需要容量上限

如果生产速度远大于消费速度，无界队列会不断膨胀。  
这时常需要有界队列：

* 队列满时，生产者阻塞或失败

```cpp
while (queue_.size() >= capacity_) {
    not_full_.wait(lock);
}
```

这样可以建立：

* 背压
* 内存上限

---

## 5. 一个更完整的阻塞队列设计

更工程化的队列通常需要这些接口：

* `push`
* `try_push`
* `pop`
* `try_pop`
* `close`

`close()` 很关键，因为消费者可能永远在等：

```cpp
if (closed_ && queue_.empty()) {
    return std::nullopt;
}
```

否则程序退出时很容易卡死在线程等待上。

---

## 6. 推荐的关闭语义

常见设计是：

* 关闭后不允许再 `push`
* 还能把队列里剩余任务消费完
* 队列空且关闭时，`pop` 返回“结束”

示意：

```cpp
std::optional<T> pop() {
    std::unique_lock<std::mutex> lk(mutex_);
    cv_.wait(lk, [&] { return closed_ || !queue_.empty(); });
    if (queue_.empty()) return std::nullopt;
    ...
}
```

这比靠塞一个 `"EXIT"` 哨兵值更通用。

---

## 7. 什么时候用 `notify_one`，什么时候用 `notify_all`

经验上：

* 普通入队，通常 `notify_one`
* 全局状态变化，比如 `close()`，通常 `notify_all`

因为关闭时可能有多个线程都在等待，需要全部唤醒重新判断。

---

## 8. 一个更稳妥的示例

```cpp
#include <condition_variable>
#include <mutex>
#include <optional>
#include <queue>

template <class T>
class BlockingQueue {
public:
    explicit BlockingQueue(std::size_t capacity) : capacity_(capacity) {}

    bool push(T value) {
        std::unique_lock<std::mutex> lk(mutex_);
        not_full_.wait(lk, [&] { return closed_ || queue_.size() < capacity_; });
        if (closed_) return false;
        queue_.push(std::move(value));
        lk.unlock();
        not_empty_.notify_one();
        return true;
    }

    std::optional<T> pop() {
        std::unique_lock<std::mutex> lk(mutex_);
        not_empty_.wait(lk, [&] { return closed_ || !queue_.empty(); });
        if (queue_.empty()) return std::nullopt;
        T value = std::move(queue_.front());
        queue_.pop();
        lk.unlock();
        not_full_.notify_one();
        return value;
    }

    void close() {
        std::lock_guard<std::mutex> lk(mutex_);
        closed_ = true;
        not_empty_.notify_all();
        not_full_.notify_all();
    }

private:
    std::size_t capacity_;
    std::queue<T> queue_;
    bool closed_ = false;
    std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
};
```

---

## 9. 阻塞队列如何安全扩容

这里的“扩容”通常指：

> 有界队列原来最多只能放 `capacity_` 个元素，现在允许它放更多元素。

扩容本身不需要搬迁队列数据，因为 `std::queue` 会自己管理内部存储。我们真正要保护的是：

* `capacity_` 的读写
* 正在等待 `not_full_` 的生产者
* 队列的关闭状态

### 9.1 最小扩容接口

可以给上面的 `BlockingQueue` 加一个 `reserve_capacity()`：

```cpp
bool reserve_capacity(std::size_t new_capacity) {
    std::unique_lock<std::mutex> lk(mutex_);

    if (closed_) {
        return false;
    }

    if (new_capacity <= capacity_) {
        return true;
    }

    capacity_ = new_capacity;
    lk.unlock();
    not_full_.notify_all();
    return true;
}
```

这里的关键点是：

* 修改 `capacity_` 必须持有同一把 `mutex_`
* 扩容后要通知等待中的生产者
* 队列已经 `close()` 后，不再允许扩容

为什么用 `notify_all()`？

因为扩容可能一次释放多个可写入位置，多个生产者都可能从“队列满”变成“可以写入”。

### 9.2 按增量扩容

有时也会写成“增加多少容量”：

```cpp
bool grow_capacity(std::size_t extra) {
    std::unique_lock<std::mutex> lk(mutex_);

    if (closed_) {
        return false;
    }

    if (extra == 0) {
        return true;
    }

    capacity_ += extra;
    lk.unlock();
    not_full_.notify_all();
    return true;
}
```

工程里还要考虑：

* 最大容量上限
* `capacity_ + extra` 是否溢出
* 是否允许扩容太频繁
* 扩容后内存压力是否可接受

否则有界队列可能又退化成“无界队列”。

### 9.3 自动扩容的思路

如果希望 `push()` 遇到满队列时自动扩容，可以把逻辑写在同一把锁里：

```cpp
bool push(T value) {
    std::unique_lock<std::mutex> lk(mutex_);
    bool expanded = false;

    if (!closed_ &&
        queue_.size() >= capacity_ &&
        capacity_ < max_capacity_) {
        capacity_ = std::min(capacity_ * 2, max_capacity_);
        expanded = true;
    }

    not_full_.wait(lk, [&] {
        return closed_ || queue_.size() < capacity_;
    });

    if (closed_) return false;

    queue_.push(std::move(value));
    lk.unlock();
    not_empty_.notify_one();
    if (expanded) {
        not_full_.notify_all();
    }
    return true;
}
```

对应成员变量可以是：

```cpp
std::size_t capacity_;
std::size_t max_capacity_;
```

如果用 `std::min`，记得包含：

```cpp
#include <algorithm>
```

这个版本的意思是：

* 队列满时，先尝试扩到更大的容量
* 如果已经到最大容量，就继续阻塞等待
* 所有判断和容量更新都在锁内完成
* 扩容后唤醒其他可能还在等待的生产者

注意不要在持锁的 `push()` 里再调用一个内部也会加锁的 `grow_capacity()`，否则很容易把自己锁死。

### 9.4 缩容要更谨慎

扩容比较简单，因为它只会让等待生产者更容易继续。

缩容更麻烦，因为可能出现：

* 当前元素数量已经超过新容量
* 生产者和消费者对“满”的判断突然变化
* 缩容策略和关闭流程互相影响

一个保守策略是：

```cpp
bool shrink_capacity(std::size_t new_capacity) {
    std::lock_guard<std::mutex> lk(mutex_);

    if (closed_) {
        return false;
    }

    if (new_capacity < queue_.size()) {
        return false;
    }

    capacity_ = new_capacity;
    return true;
}
```

也就是说：

> 不把容量缩到当前队列大小以下。

这样可以避免队列瞬间进入一种“已经超载但无法解释”的状态。

---

## 10. 常见坑

### 10.1 `if` 代替 `while`/谓词

这是最常见的条件变量错误。

### 10.2 持锁太久

如果拿着锁做重计算或 I/O，会严重拖慢并发吞吐。

### 10.3 没有关闭语义

线程可能永远阻塞退出不了。

### 10.4 用哨兵值替代通用关闭协议

对简单 demo 可以，但扩展性差。

---

## 11. 一页总结

生产者-消费者模式的核心不是“有个队列”，而是：

1. 用互斥保护共享队列
2. 用条件变量等待状态变化
3. 用关闭协议管理线程退出
4. 必要时用容量上限建立背压
5. 动态扩容时，要在同一把锁内修改容量并唤醒等待生产者

如果只记一句：

> 条件变量永远和“共享状态 + 谓词检查”一起使用，不能只靠通知本身。

---

# [05]线程同步消息队列与线程池

# 线程同步消息队列与线程池

时间：2026/04/09

> 关键词：任务队列、worker thread、`future`、停止协议、背压、线程池  
> 核心目标：理解线程池为什么几乎总是“队列 + 工作线程 + 生命周期管理”的组合。

---

## 1. 为什么线程池比“每个任务一个线程”更常见

直接为每个任务创建线程的问题在于：

* 创建销毁开销高
* 线程数不可控
* 容易把系统调度器压爆

线程池的思路是：

* 预先创建固定数量 worker
* 任务进入共享队列
* worker 从队列取任务执行

---

## 2. 线程池最小结构

一个线程池通常包含：

* 任务队列
* 多个工作线程
* 停止标志
* 提交接口

示意：

```text
producer -> task queue -> workers
```

---

## 3. 推荐的任务表示

最常见的是：

```cpp
std::function<void()>
```

这样线程池不关心任务具体类型，只负责执行。

如果要返回值，可以把真实任务包装进：

* `std::packaged_task`
* `std::promise`
* `std::future`

---

## 4. 一个最小线程池骨架

```cpp
#include <condition_variable>
#include <functional>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

class ThreadPool {
public:
    explicit ThreadPool(std::size_t n) {
        for (std::size_t i = 0; i < n; ++i) {
            workers_.emplace_back([this] { worker_loop(); });
        }
    }

    ~ThreadPool() {
        {
            std::lock_guard<std::mutex> lk(mutex_);
            stop_ = true;
        }
        cv_.notify_all();
        for (auto& t : workers_) {
            if (t.joinable()) t.join();
        }
    }

    void submit(std::function<void()> task) {
        {
            std::lock_guard<std::mutex> lk(mutex_);
            tasks_.push(std::move(task));
        }
        cv_.notify_one();
    }

private:
    void worker_loop() {
        while (true) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> lk(mutex_);
                cv_.wait(lk, [&] { return stop_ || !tasks_.empty(); });
                if (stop_ && tasks_.empty()) return;
                task = std::move(tasks_.front());
                tasks_.pop();
            }
            task();
        }
    }

    bool stop_ = false;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::queue<std::function<void()>> tasks_;
    std::vector<std::thread> workers_;
};
```

---

## 5. 为什么停止协议很重要

如果没有明确的停止逻辑，线程池很容易在析构时：

* worker 永远等在 `wait`
* 主线程 join 不回来

正确退出条件通常是：

* `stop_ == true`
* 并且队列已空

---

## 6. 返回值怎么做

常见写法是：

* 把用户任务包装成 `packaged_task`
* 返回对应 `future`

这样提交方既能异步执行，也能之后 `get()` 结果。

线程池的接口常见长这样：

```cpp
template <class F, class... Args>
auto enqueue(F&& f, Args&&... args) -> std::future<...>;
```

这也是完美转发的高频实战场景。

---

## 7. 有界任务队列与背压

如果任务生产速度远大于消费速度，线程池也可能把内存吃爆。  
所以工程上经常要考虑：

* 队列容量上限
* 超限后阻塞
* 超限后丢弃
* 超限后降级

这其实就是背压策略。

---

## 8. 线程池不是越多线程越好

线程数通常取决于：

* CPU 核心数
* 任务是否 CPU 密集
* 任务是否经常阻塞 I/O

经验上：

* CPU 密集型：线程数通常接近核心数
* I/O 密集型：线程数可适当更大

---

## 9. 线程池如何安全扩容

线程池扩容的本质是：

> 在不破坏任务队列、不影响已有 worker、不和析构/停止流程打架的前提下，增加新的 worker 线程。

只“扩容”通常比“缩容”简单，因为扩容不需要强行打断已有线程，只需要让更多线程开始消费同一个任务队列。

### 9.1 安全扩容要守住的几个点

1. 扩容时要和停止状态互斥
2. 新 worker 必须复用同一套 `worker_loop`
3. 不要在任务执行期间持有队列锁
4. 不允许线程池已经停止后继续扩容
5. 如果有最大线程数，要在锁内检查和更新

最核心的判断是：

```cpp
if (stop_) {
    throw std::runtime_error("thread pool already stopped");
}
```

否则可能出现这种危险情况：

1. 析构线程设置 `stop_ = true`
2. 另一个线程又新增 worker
3. 析构只 join 了旧线程或生命周期已经混乱

### 9.2 一个简单的扩容接口

可以给线程池加一个 `add_workers()`：

```cpp
void add_workers(std::size_t count) {
    std::lock_guard<std::mutex> lk(mutex_);

    if (stop_) {
        throw std::runtime_error("thread pool already stopped");
    }

    for (std::size_t i = 0; i < count; ++i) {
        workers_.emplace_back([this] { worker_loop(); });
    }
}
```

这段代码的关键点是：

* `stop_` 和 `workers_` 的修改放在同一把锁保护下
* 新线程执行的还是原来的 `worker_loop()`
* 新 worker 会自动从同一个 `tasks_` 队列里抢任务

不过这只是最小写法。正式项目里通常还会加：

* `max_workers_`
* 当前线程数统计
* 扩容失败处理
* 线程池生命周期约束

### 9.3 带最大线程数的版本

更工程化一点：

```cpp
void add_workers(std::size_t count) {
    std::lock_guard<std::mutex> lk(mutex_);

    if (stop_) {
        throw std::runtime_error("thread pool already stopped");
    }

    const std::size_t current = workers_.size();
    const std::size_t allowed = max_workers_ > current
        ? max_workers_ - current
        : 0;

    const std::size_t actual = std::min(count, allowed);

    for (std::size_t i = 0; i < actual; ++i) {
        workers_.emplace_back([this] { worker_loop(); });
    }
}
```

对应成员变量：

```cpp
std::size_t max_workers_ = std::thread::hardware_concurrency() * 2;
```

这里的重点不是公式，而是：

> 扩容不能无限扩，否则线程池会退化成“每个任务都创建线程”的混乱状态。

### 9.4 扩容后需要 `notify_all()` 吗

通常不一定需要。

因为新 worker 创建后会进入 `worker_loop()`，它自己会检查队列：

```cpp
cv_.wait(lk, [&] { return stop_ || !tasks_.empty(); });
```

如果队列里已经有任务，谓词为真，新 worker 不会一直睡着。

但如果你的实现不是带谓词的 `wait`，或者扩容逻辑还改变了其他调度状态，就要重新检查通知逻辑。

### 9.5 自动扩容的常见触发条件

如果做成动态线程池，常见策略是：

* 队列积压超过阈值
* 当前线程数小于最大线程数
* 最近一段时间任务消费速度跟不上提交速度
* 任务是 I/O 密集型，worker 经常阻塞

伪代码：

```cpp
if (tasks_.size() > high_watermark &&
    workers_.size() < max_workers_) {
    add_workers(1);
}
```

注意这个判断必须在锁保护下完成，避免多个提交线程同时发现“需要扩容”，然后一起扩太多。

### 9.6 缩容比扩容更麻烦

扩容是“增加消费者”，一般比较安全。

缩容是“让某些 worker 退出”，要设计额外协议，例如：

* 空闲超时退出
* 投递特殊退出任务
* 设置目标线程数，让多余 worker 在空闲时自然退出

不要粗暴强杀线程。C++ 标准线程没有安全的强制 kill 机制，强行终止线程很容易破坏锁、资源和对象状态。

---

## 10. 消息队列 vs 线程池

这两个概念经常一起出现，但不完全一样。

* 消息队列：强调数据传递与同步
* 线程池：强调任务执行与线程复用

线程池内部几乎总会用到任务队列，但消息队列本身不一定等于线程池。

---

## 11. 常见坑

### 11.1 任务里抛异常没人管

如果没有 `future` 或显式捕获，异常可能直接导致线程终止。

### 11.2 析构时仍允许提交任务

这会让生命周期变得混乱。

### 11.3 持锁执行任务

这是严重错误。  
正确做法是：

* 取出任务后释放锁
* 再执行任务

### 11.4 线程池里再无限提交内部任务

这可能制造级联膨胀和死锁风险。

---

## 12. 一页总结

线程池最关键的不是模板技巧，而是三个工程点：

1. 任务队列
2. worker 生命周期
3. 明确的停止与背压策略

如果只记一句：

> 线程池本质上是“用受控线程数去消费一个受控任务流”。

---

# [06]工厂模式、多态与接口设计

# 工厂模式、多态与接口设计

时间：2026/04/09

> 关键词：抽象接口、虚函数、工厂函数、依赖倒置、`override`、虚析构、`unique_ptr`  
> 核心目标：理解什么时候该把“创建对象”和“使用对象”分开。

---

## 1. 为什么需要工厂模式

很多代码的问题不是“不会 new”，而是：

* 调用方知道太多具体类型
* 构造逻辑散落各处
* 后续替换实现很痛苦

工厂模式的核心价值是：

* 把对象创建逻辑集中起来
* 让调用方依赖抽象接口，而不是具体实现

---

## 2. 多态接口的基础

```cpp
struct Pet {
    virtual ~Pet() = default;
    virtual void speak() = 0;
};

struct Cat : Pet {
    void speak() override { std::puts("meow"); }
};

struct Dog : Pet {
    void speak() override { std::puts("woof"); }
};
```

这里要点有两个：

* 基类析构函数要么虚，要么不允许多态删除
* 派生类重写时用 `override`

---

## 3. 一个最简单的工厂函数

```cpp
#include <memory>
#include <string>

std::unique_ptr<Pet> make_pet(const std::string& kind) {
    if (kind == "cat") return std::make_unique<Cat>();
    if (kind == "dog") return std::make_unique<Dog>();
    return nullptr;
}
```

调用方只关心：

* 我要一个 `Pet`

而不关心：

* 具体怎么构造 `Cat` / `Dog`

---

## 4. 为什么返回 `unique_ptr`

返回裸指针会引入一个问题：

* 谁负责 `delete`

用 `std::unique_ptr` 更清晰：

* 工厂负责创建
* 调用方接管独占所有权

这是现代 C++ 工厂接口最常见的实践。

---

## 5. 简单工厂 vs 工厂方法

### 5.1 简单工厂

一个集中函数，根据参数分支创建对象。

优点：

* 简单直接

缺点：

* 新增类型时可能要改原工厂

### 5.2 工厂方法

把“创建哪种对象”交给子类。

适合：

* 框架式扩展
* 产品族较复杂

但对小项目来说，简单工厂已经够用。

---

## 6. 接口设计比模式名更重要

真正工程里，更该关注这些问题：

* 基类是不是表达了稳定抽象
* 调用方是否真的不需要知道具体类型
* 返回所有权是否清晰
* 是否需要注册表或插件化

很多时候模式本身不复杂，难的是接口边界。

---

## 7. 一个更贴近工程的例子

```cpp
struct Reducer {
    virtual ~Reducer() = default;
    virtual int init() const = 0;
    virtual int combine(int a, int b) const = 0;
};

struct SumReducer : Reducer {
    int init() const override { return 0; }
    int combine(int a, int b) const override { return a + b; }
};

struct MulReducer : Reducer {
    int init() const override { return 1; }
    int combine(int a, int b) const override { return a * b; }
};
```

这里“算法骨架”不变，“聚合策略”可替换。  
这类设计常和工厂、策略模式一起出现。

---

## 8. 工厂模式的常见扩展

### 8.1 注册表工厂

把字符串或类型 id 映射到创建函数：

* 更适合插件化
* 更适合可扩展系统

### 8.2 抽象工厂

如果你需要创建一整组关联对象，就可能进入抽象工厂场景。

例如：

* UI 皮肤
* 跨平台组件族

---

## 9. 常见坑

### 9.1 基类没有虚析构

多态删除会出问题。

### 9.2 工厂返回裸指针

所有权不清晰。

### 9.3 为了“用模式而用模式”

小项目里过度抽象只会增加复杂度。

### 9.4 基类接口设计得太宽

会让派生类被迫实现很多并不需要的东西。

---

## 10. 参考实例：注册表工厂

当对象类型会扩展时，可以用“名字 -> 创建函数”的注册表。  
调用方只依赖抽象接口，不需要知道具体类。

```cpp
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>

struct Shape {
    virtual ~Shape() = default;
    virtual double area() const = 0;
};

struct Circle : Shape {
    explicit Circle(double r) : r(r) {}
    double area() const override { return 3.14159 * r * r; }
    double r = 1.0;
};

struct Square : Shape {
    explicit Square(double side) : side(side) {}
    double area() const override { return side * side; }
    double side = 1.0;
};

class ShapeFactory {
public:
    using Creator = std::function<std::unique_ptr<Shape>(double)>;

    void register_type(std::string name, Creator creator) {
        creators_[std::move(name)] = std::move(creator);
    }

    std::unique_ptr<Shape> create(std::string_view name, double arg) const {
        auto it = creators_.find(std::string(name));
        if (it == creators_.end()) {
            throw std::runtime_error("unknown shape type");
        }
        return it->second(arg);
    }

private:
    std::unordered_map<std::string, Creator> creators_;
};

int main() {
    ShapeFactory factory;

    factory.register_type("circle", [](double r) {
        return std::make_unique<Circle>(r);
    });

    factory.register_type("square", [](double side) {
        return std::make_unique<Square>(side);
    });

    auto shape = factory.create("circle", 2.0);
    double a = shape->area();
}
```

这个例子里：

* 工厂集中管理创建逻辑
* 返回 `unique_ptr` 表达所有权转移
* 新类型只需要注册，不需要改调用方
* 运行期根据字符串选择具体类型

---

## 11. 一页总结

工厂模式最核心的收益不是“设计模式名词”，而是：

1. 创建逻辑集中
2. 调用方依赖抽象
3. 所有权表达清晰

如果只记一句：

> 当“对象怎么创建”开始影响“对象怎么使用”时，就该考虑把创建逻辑抽出来。

---

# [07]游戏常见设计模式

# 游戏常见设计模式

时间：2026/04/09

> 关键词：单例、状态模式、命令模式、观察者、组件化、对象池  
> 核心目标：从游戏开发常见场景出发，理解哪些模式真的有用，以及哪些模式容易被滥用。

---

## 1. 游戏代码为什么特别容易模式化

游戏逻辑常见特点：

* 实体多
* 状态多
* 事件多
* 生命周期复杂
* 性能敏感

因此很多经典模式在游戏里非常常见，但也特别容易被滥用。

---

## 2. 单例模式：能用，但要克制

单例通常用于：

* 配置中心
* 日志系统
* 全局资源管理器

最简单安全的写法通常是局部静态：

```cpp
class GameConfig {
public:
    static GameConfig& instance() {
        static GameConfig cfg;
        return cfg;
    }

private:
    GameConfig() = default;
};
```

优点：

* 简单
* 线程安全初始化

缺点：

* 全局依赖隐蔽
* 测试困难
* 生命周期难拆

所以经验上：

* 单例适合少量基础设施，不适合把一切都做成全局对象

---

## 3. 状态模式：替代大 `switch`

当一个角色会在多种状态之间切换，例如：

* Idle
* Chase
* Attack
* Dead

如果全写在一个大 `switch` 里，代码会越来越乱。  
状态模式的思路是：

* 每个状态自己负责更新逻辑和转移条件

```cpp
struct Monster;

struct State {
    virtual ~State() = default;
    virtual void update(Monster& m) = 0;
};
```

这样“状态行为”会比“状态枚举 + 大分支”更容易扩展。

---

## 4. 命令模式：把输入和行为解耦

适用场景：

* 输入映射
* 回放系统
* AI 行为排队
* 网络同步操作记录

基本思路：

* 把“做什么”封装成命令对象

```cpp
struct Command {
    virtual ~Command() = default;
    virtual void execute() = 0;
};
```

这样可以做到：

* 排队执行
* 延迟执行
* 撤销/重放

---

## 5. 观察者 / 事件模式

适合：

* UI 更新
* 成就系统
* 音效触发
* 状态广播

思路是：

* 某个系统发事件
* 多个订阅者响应

优点：

* 降低模块直接耦合

风险：

* 调用链变隐蔽
* 调试困难

所以事件系统要控制好：

* 事件粒度
* 生命周期
* 订阅关系

---

## 6. 组件化 / ECS 思路

传统继承层级：

* `Monster -> BossMonster -> FlyingBossMonster -> ...`

很容易爆炸。  
组件化更偏向：

* Position
* Render
* Physics
* Health

通过组合形成实体能力。

这样更灵活，也更适合：

* 数据驱动
* 批量更新
* SoA / cache 友好设计

---

## 7. 对象池：减少频繁分配

游戏里这些对象往往高频创建销毁：

* 子弹
* 粒子
* 临时特效

如果每次都 `new/delete`，可能带来：

* 分配开销
* 碎片
* 抖动

对象池的思路是：

* 提前分配一批对象
* 使用时取出
* 用完后归还

但要注意：

* 池化会增加状态管理复杂度
* 不是所有对象都值得池化

---

## 8. 模板方法模式

适用于：

* 主流程固定
* 个别步骤由派生类决定

例如角色更新：

```cpp
struct Character {
    virtual ~Character() = default;
    virtual void think() = 0;
    virtual void move() = 0;
    virtual void draw() = 0;

    void update() {
        think();
        move();
        draw();
    }
};
```

这种模式的优点是流程稳定，但要避免基类职责过重。

---

## 9. 游戏开发里最常见的误区

### 9.1 什么都做成单例

最后会形成巨型全局依赖网。

### 9.2 继承层级过深

很多时候组合比继承更稳。

### 9.3 事件系统滥用

会让控制流难以追踪。

### 9.4 为了模式而模式

很多小项目只需要清晰结构，不需要把所有经典模式全搬进来。

---

## 10. 参考实例：对象池管理子弹

游戏里子弹、粒子、临时特效经常大量创建和销毁。  
对象池可以把频繁分配变成复用。

```cpp
#include <optional>
#include <cstddef>
#include <vector>

struct Bullet {
    bool active = false;
    float x = 0.0f;
    float y = 0.0f;
    float vx = 0.0f;
    float vy = 0.0f;
    float life = 0.0f;
};

class BulletPool {
public:
    explicit BulletPool(std::size_t capacity)
        : bullets_(capacity) {}

    Bullet* spawn(float x, float y, float vx, float vy) {
        for (auto& b : bullets_) {
            if (!b.active) {
                b = Bullet{
                    .active = true,
                    .x = x,
                    .y = y,
                    .vx = vx,
                    .vy = vy,
                    .life = 2.0f,
                };
                return &b;
            }
        }

        return nullptr; // 池满，可以选择丢弃或扩容
    }

    void update(float dt) {
        for (auto& b : bullets_) {
            if (!b.active) {
                continue;
            }

            b.x += b.vx * dt;
            b.y += b.vy * dt;
            b.life -= dt;

            if (b.life <= 0.0f) {
                b.active = false;
            }
        }
    }

    const std::vector<Bullet>& bullets() const {
        return bullets_;
    }

private:
    std::vector<Bullet> bullets_;
};
```

这个例子体现了对象池的几个取舍：

* 分配次数少，运行时更稳定
* 对象地址相对稳定
* 需要显式维护 active 状态
* 池满策略必须提前设计

---

## 11. 一页总结

游戏里真正常用、且值得优先掌握的几个模式是：

1. 状态模式
2. 命令模式
3. 观察者 / 事件模式
4. 组件化 / ECS
5. 对象池

单例不是不能用，但一定要克制。

如果只记一句：

> 游戏模式的价值不在“名词多高级”，而在于它能不能降低复杂状态和高频对象管理的混乱度。

---

# [08]对象布局、栈堆与未定义行为

# 对象布局、栈堆与未定义行为

时间：2026/04/09

> 关键词：栈、堆、静态区、对齐、padding、悬空指针、越界、strict aliasing  
> 核心目标：建立“对象怎么放在内存里”的正确直觉，避免把现代 C++ 写成偶发崩溃的未定义行为集合。

---

## 1. 栈和堆最容易被误解的点

简单说：

* 栈：作用域驱动的自动存储
* 堆：动态分配、手动或 RAII 管理

但更准确的重点不是“栈连续还是不连续”，而是：

* 对象生命周期
* 所有权
* 是否发生悬空和越界

---

## 2. 常见内存区域

粗略理解：

* 代码区
* 全局/静态区
* 栈
* 堆

局部变量通常在栈上：

```cpp
int x = 1;
```

动态分配通常在堆上：

```cpp
auto p = std::make_unique<int>(42);
```

---

## 3. 栈对象的最大优点

栈对象最大优点不是“快”这一个字，而是：

* 生命周期清晰
* 自动析构
* 适合 RAII

所以现代 C++ 的默认倾向是：

* 能值语义就值语义
* 能局部对象就局部对象

---

## 4. 栈对象最大的风险

不是“栈内存不连续”，而是：

* 返回局部变量地址
* 返回局部引用
* 离开作用域后继续访问

```cpp
int* bad() {
    int x = 1;
    return &x; // 错
}
```

---

## 5. 堆对象的价值和代价

堆对象适合：

* 跨作用域存活
* 运行期决定大小
* 多态对象

代价是：

* 需要明确所有权
* 分配释放有开销
* 更容易泄漏或悬空

所以：

* 堆不是默认选项
* 只有确实需要时才动态分配

---

## 6. 对齐与 padding

对象内存布局受类型对齐影响。

```cpp
struct A {
    char c;
    int x;
};
```

`sizeof(A)` 往往不只是 5，而可能是 8。  
原因是：

* 编译器会插入 padding 满足对齐要求

这会影响：

* 内存占用
* 缓存利用率
* 二进制布局

---

## 7. 未定义行为最常见的几类

### 7.1 越界访问

```cpp
int a[4];
int x = a[10];
```

### 7.2 悬空指针

```cpp
int* p = new int(1);
delete p;
*p = 2; // 错
```

### 7.3 错误类型解释

```cpp
double d = 3.14;
int* p = reinterpret_cast<int*>(&d); // 极危险
```

### 7.4 严格别名相关问题

某些类型转换会让编译器优化假设失效。

---

## 8. 为什么现代 C++ 强调封装

很多底层问题不是“不允许碰”，而是：

* 一旦你直接操作裸内存，就必须承担全部正确性责任

所以现代实践更推荐：

* `std::vector`
* `std::string`
* `std::array`
* `std::span`
* 智能指针

来包住底层细节。

---

## 9. 一页总结

最重要的三条：

1. 栈对象优先，因为生命周期最清晰
2. 堆对象只有在确实需要动态生命周期时才用
3. 越界、悬空、错误类型解释都不是“小问题”，而是未定义行为

如果只记一句：

> 现代 C++ 不是不让你碰底层，而是要求你在碰底层时明确对象生命周期和内存语义。

---

# [09]网络服务基础：TCP粘包、线程模型与HTTP(S)

# 网络服务基础：TCP 粘包、线程模型与 HTTP(S)

时间：2026/04/09

> 关键词：TCP stream、粘包拆包、长度前缀、分隔符、线程池、epoll、TLS、wrk  
> 核心目标：建立服务端编程的基本工程直觉，先把“消息边界、并发模型、协议分层”分清楚。

---

## 1. TCP 为什么会有“粘包”问题

因为 TCP 是**字节流**，不是消息流。

这意味着：

* 发送端发了两次 `send`
* 接收端不一定就对应收到两次 `recv`

接收端看到的只是连续字节流，所以必须自己定义消息边界。

---

## 2. 两种最常见的拆包方案

### 2.1 长度前缀

格式示例：

```text
[4字节长度][payload]
```

接收端流程：

1. 先读够头部
2. 解析长度
3. 再继续读够 payload

这通常是最通用、最可靠的做法。

### 2.2 分隔符协议

例如按 `\n` 分隔：

```text
hello\nworld\n
```

优点：

* 简单直观

缺点：

* payload 中若可能出现分隔符，需要转义或编码

---

## 3. 长度前缀接收缓冲的核心思路

接收端通常需要一个累积缓冲区：

```cpp
std::vector<std::uint8_t> inbuf;
```

每次 `recv` 到数据后：

* 先追加到 `inbuf`
* 再循环解析完整包

关键不是“每次只解析一个包”，而是：

* 一次 `recv` 可能带来 0.5 个包、1 个包、或者多个包

---

## 4. 为什么不能假设一次 `recv` 就是一条完整消息

因为可能出现：

* 半包
* 多包合并
* 多次拆散

所以网络编程第一条纪律就是：

> 任何协议都必须先定义并实现消息 framing。

---

## 5. 线程模型的几种常见选择

### 5.1 每连接一个线程

优点：

* 思维简单

缺点：

* 连接数一大就撑不住

### 5.2 单线程事件循环

优点：

* 资源利用率高

缺点：

* 业务阻塞会拖住整个 loop

### 5.3 Reactor + 线程池

常见工程做法：

* I/O 线程负责收发和事件分发
* 工作线程池处理业务

这样可以同时兼顾：

* 网络扩展性
* 业务并发

---

## 6. `epoll` / `kqueue` / IOCP` 在解决什么问题

这些机制本质上都在解决：

* 如何高效等待大量连接上的 I/O 事件

Linux 上最常见的是：

* `epoll`

它不是协议，也不是线程池，而是：

* 一个事件通知机制

---

## 7. HTTP 和 HTTPS 不要混成一层

### 7.1 HTTP

应用层协议，定义：

* 请求行
* 头部
* body

### 7.2 HTTPS

可以粗略理解成：

* HTTP over TLS

也就是：

* 先做 TLS 加密通道
* 再在其上跑 HTTP

所以 HTTPS 的复杂度不仅来自 HTTP，还来自：

* 握手
* 证书
* 加解密

---

## 8. 一个服务端最基础的工程分层

可以先按这几层理解：

1. socket 层
2. 缓冲区与 framing 层
3. 协议解析层
4. 业务处理层
5. 线程模型 / 调度层

很多初学者的问题是把所有逻辑都揉进一次 `recv` 回调里，后期几乎无法维护。

---

## 9. 线程池在网络服务里的角色

网络服务中，线程池通常不应该负责：

* 直接阻塞式读写所有 socket

更常见的是负责：

* 处理业务任务
* 数据库访问
* CPU 密集计算
* 日志/异步处理

也就是说：

* I/O 线程负责“把事情收进来”
* 线程池负责“把事情做完”

---

## 10. TLS / HTTPS 的最小认知

只要记住这几点就够做入门框架理解：

* TLS 负责加密通道
* 证书用于身份认证
* HTTPS 不是“新的 HTTP 消息格式”，而是多了一层安全传输

工程上常见做法是：

* 直接用成熟库处理 TLS
* 不自己从零实现加密协议

---

## 11. 压测为什么重要

服务端“能跑”不等于“能扛”。  
至少要关注：

* QPS
* 延迟
* P99
* 错误率
* CPU / 内存占用

`wrk` 是一个常用 HTTP 压测工具，适合快速做吞吐和延迟观察。

---

## 12. 常见坑

### 12.1 把 TCP 当消息协议

这会直接导致粘包拆包错误。

### 12.2 收到数据就立刻假设包完整

半包是常态，不是例外。

### 12.3 网络线程直接做重业务

会拖慢整个事件循环。

### 12.4 自己手写 TLS 协议栈

不现实，也没必要。

---

## 13. 参考实例：长度前缀拆包器

TCP 是字节流，所以接收缓冲里可能一次来半包、多包或任意切分。  
下面是一个最小长度前缀协议解析器：前 4 字节是大端 payload 长度。

```cpp
#include <cstdint>
#include <cstddef>
#include <optional>
#include <span>
#include <stdexcept>
#include <vector>

class FrameDecoder {
public:
    void append(std::span<const std::byte> bytes) {
        buffer_.insert(buffer_.end(), bytes.begin(), bytes.end());
    }

    std::optional<std::vector<std::byte>> next_frame() {
        if (buffer_.size() < header_size) {
            return std::nullopt;
        }

        std::uint32_t len = read_u32_be(buffer_.data());
        if (len > max_frame_size) {
            throw std::runtime_error("frame too large");
        }

        const std::size_t total = header_size + len;
        if (buffer_.size() < total) {
            return std::nullopt;
        }

        std::vector<std::byte> payload(
            buffer_.begin() + header_size,
            buffer_.begin() + static_cast<std::ptrdiff_t>(total)
        );

        buffer_.erase(
            buffer_.begin(),
            buffer_.begin() + static_cast<std::ptrdiff_t>(total)
        );

        return payload;
    }

private:
    static constexpr std::size_t header_size = 4;
    static constexpr std::uint32_t max_frame_size = 1024 * 1024;

    static std::uint32_t read_u32_be(const std::byte* p) {
        return (std::uint32_t(std::to_integer<unsigned char>(p[0])) << 24) |
               (std::uint32_t(std::to_integer<unsigned char>(p[1])) << 16) |
               (std::uint32_t(std::to_integer<unsigned char>(p[2])) << 8)  |
                std::uint32_t(std::to_integer<unsigned char>(p[3]));
    }

    std::vector<std::byte> buffer_;
};
```

使用方式通常是：

```cpp
FrameDecoder decoder;

// 每次 recv 得到一段 bytes 后：
decoder.append(bytes);

while (auto frame = decoder.next_frame()) {
    handle_message(*frame);
}
```

关键点：

* `append()` 不假设一次收到完整消息
* `next_frame()` 可能返回空，表示还需要更多字节
* 解出一帧后要从缓冲区移除已经消费的数据
* 必须限制最大包大小，避免恶意长度导致内存暴涨

---

## 14. 一页总结

服务端编程最重要的理解链是：

1. TCP 只有字节流，没有消息边界
2. 所以必须先做 framing
3. 高并发服务通常要把 I/O 与业务处理分层
4. HTTPS = HTTP + TLS，不是单纯“更安全的 socket”

如果只记一句：

> 网络服务首先是“协议边界和并发模型”问题，其次才是 API 调用问题。

---

# [10]C++20协程入门与实践

# C++20 协程入门与实践

时间：2026/04/09

> 关键词：`co_await`、`co_return`、`co_yield`、`promise_type`、`coroutine_handle`、协程帧、挂起点、恢复点、awaitable、generator、异步 I/O
> 核心目标：理解 C++20 协程不是“轻量线程”，而是“编译器把可暂停函数改写成状态机”的语言机制；真正工程难点在生命周期、调度器、恢复线程、异常传播和取消。

---

## 1. 协程到底解决什么问题

传统异步代码常见两个问题：

* 回调层层嵌套，业务流程被拆散。
* 手写状态机很繁琐，容易遗漏状态、错误和资源释放。

例如一个异步流程：

```text
发起连接
  -> 等连接完成
  -> 发请求
  -> 等响应
  -> 解析响应
  -> 写数据库
```

回调写法可能变成：

```cpp
async_connect([&](Error ec) {
    if (ec) return handle_error(ec);

    async_write(request, [&](Error ec) {
        if (ec) return handle_error(ec);

        async_read([&](Error ec, Response resp) {
            if (ec) return handle_error(ec);

            parse(resp, [&](Parsed parsed) {
                save_to_db(parsed);
            });
        });
    });
});
```

协程希望把它写得接近同步流程：

```cpp
Task<void> request_flow() {
    co_await async_connect();
    co_await async_write(request);
    auto resp = co_await async_read();
    auto parsed = parse(resp);
    co_await save_to_db(parsed);
}
```

注意这只是“写法像同步”，并不代表它真的阻塞线程。

协程的核心价值：

* 把“会暂停、稍后恢复”的流程写成顺序代码。
* 让编译器自动生成状态机。
* 避免手写大量 callback 和状态变量。

一句话：

> C++20 协程解决的是异步控制流表达问题，不是自动解决并发、调度、线程安全问题。

---

## 2. 协程不是线程

这点非常重要。

协程：

* 默认不并行。
* 默认不创建线程。
* 默认不自动切线程。
* 只是一个可以挂起和恢复的函数。
* 挂起后，当前线程可以去做别的事。

线程：

* 是操作系统调度实体。
* 可以真正并行执行。
* 有独立调用栈。
* 创建、切换、同步成本更高。

对比：

| 维度 | 协程 | 线程 |
| --- | --- | --- |
| 调度者 | 由程序/运行时决定 | 操作系统 |
| 是否自动并行 | 否 | 是 |
| 是否有独立 OS 栈 | C++20 无栈协程，没有独立 OS 栈 | 有 |
| 适合解决 | 异步流程组织、生成器、状态机 | 并行执行、阻塞任务 |
| 典型开销 | 协程帧分配、恢复调用 | 线程栈、内核调度 |

协程解决的是：

```text
这段逻辑执行到这里可以先停下来，之后从这里继续。
```

线程解决的是：

```text
这段逻辑要和其他逻辑同时执行。
```

所以不要说：

> 协程是轻量线程。

更准确的说法是：

> C++20 协程是语言级可挂起函数，常被异步运行时用来表达非阻塞流程。

---

## 3. 什么函数会变成协程

只要函数体里出现下面任意一个关键字，它就是协程：

* `co_await`
* `co_return`
* `co_yield`

例如：

```cpp
Task<void> f() {
    co_return;
}
```

即使没有真正异步等待，只要出现 `co_return`，这个函数就是协程。

普通函数：

```cpp
int add(int a, int b) {
    return a + b;
}
```

协程函数：

```cpp
Task<int> add_async(int a, int b) {
    co_return a + b;
}
```

注意：

* 协程函数不能使用普通 `return value;` 返回结果。
* 协程里要用 `co_return value;`。
* 协程返回类型不是随便写的，它必须和 `promise_type` 配合。

---

## 4. 三个关键字

### 4.1 `co_await`

等待一个可等待对象。

```cpp
auto result = co_await something;
```

它可能：

* 立即返回结果，不挂起。
* 挂起当前协程，稍后恢复。
* 恢复后返回一个值或抛出异常。

### 4.2 `co_return`

从协程返回。

```cpp
co_return;
co_return 42;
```

它最终会调用 `promise_type` 里的：

```cpp
return_void()
return_value(value)
```

### 4.3 `co_yield`

逐个产出值，常用于生成器。

```cpp
Generator<int> range(int n) {
    for (int i = 0; i < n; ++i) {
        co_yield i;
    }
}
```

它最终会调用 `promise_type` 里的：

```cpp
yield_value(value)
```

---

## 5. 编译器视角：协程会被改写成什么

当编译器看到协程函数，它大致会改写成一个状态机。

源码看起来像：

```cpp
Task<void> f() {
    step1();
    co_await wait_something();
    step2();
    co_return;
}
```

编译器背后大致变成：

```text
创建协程帧
创建 promise 对象
保存局部变量
记录当前执行到哪个挂起点
遇到 co_await 时保存状态并返回
之后通过 coroutine_handle::resume() 从挂起点继续执行
```

可以粗略理解成：

```cpp
switch (state) {
case 0:
    step1();
    state = 1;
    suspend();
    return;

case 1:
    step2();
    finish();
    return;
}
```

这也是为什么协程能“暂停再继续”：

* 局部变量被保存在协程帧里。
* 当前执行位置被记录下来。
* 恢复时从上次挂起点继续。

---

## 6. 协程帧是什么

协程帧可以理解成协程的运行时状态对象。

它通常保存：

* `promise_type` 对象。
* 跨挂起点仍然活着的局部变量。
* 参数副本。
* 当前挂起位置。
* 异常状态。
* 返回值。

普通函数的局部变量通常在栈上：

```cpp
void f() {
    int x = 1;
}
```

函数返回后，栈帧消失。

但协程可能在中间挂起：

```cpp
Task<void> f() {
    int x = 1;
    co_await something;
    use(x);
}
```

`x` 必须在挂起后仍然存在，所以它会进入协程帧。

协程帧通常分配在堆上，但标准并不强制必须堆分配，编译器在能证明生命周期的情况下可以优化。

重点：

> 协程不是把普通函数栈保存起来，而是编译器生成一个可恢复的状态对象。

---

## 7. `std::coroutine_handle`

`std::coroutine_handle<>` 是恢复和销毁协程帧的句柄。

常用操作：

```cpp
handle.resume();   // 恢复执行
handle.done();     // 是否已经完成
handle.destroy();  // 销毁协程帧
```

带 promise 类型的 handle：

```cpp
std::coroutine_handle<promise_type>
```

可以访问 promise：

```cpp
handle.promise()
```

你可以把它理解成：

```text
coroutine_handle 指向协程帧；
promise 是协程帧中用于和外部交互的控制对象。
```

最重要的工程点：

> 谁拿着 `coroutine_handle`，谁就间接掌握了协程恢复和销毁的能力。

所以要非常小心生命周期。

---

## 8. `promise_type` 是什么

如果一个类型想作为协程返回类型，需要有配套的 `promise_type`。

例如：

```cpp
struct Task {
    struct promise_type {
        ...
    };
};
```

`promise_type` 决定：

* 协程返回对象怎么创建。
* 协程开始时是否立刻执行。
* 协程结束时是否挂起。
* `co_return` 怎么保存结果。
* `co_yield` 怎么产出结果。
* 未捕获异常怎么处理。

常见接口：

```cpp
struct promise_type {
    Task get_return_object();
    std::suspend_always initial_suspend() noexcept;
    std::suspend_always final_suspend() noexcept;
    void return_void();
    void unhandled_exception();
};
```

如果有返回值：

```cpp
void return_value(int value);
```

如果支持 `co_yield`：

```cpp
std::suspend_always yield_value(int value);
```

---

## 9. `initial_suspend` 和 `final_suspend`

这两个函数决定协程开始和结束时是否挂起。

### 9.1 `initial_suspend`

协程创建后，是否立刻执行函数体。

```cpp
std::suspend_never initial_suspend() noexcept { return {}; }
```

表示创建后马上执行。

```cpp
std::suspend_always initial_suspend() noexcept { return {}; }
```

表示创建后先挂起，等外部手动 `resume()`。

这两种模式常叫：

* eager coroutine：创建后立刻执行。
* lazy coroutine：创建后不执行，等别人启动。

### 9.2 `final_suspend`

协程执行完后，是否在最终点挂起。

如果返回对象还持有 `coroutine_handle`，通常要：

```cpp
std::suspend_always final_suspend() noexcept { return {}; }
```

这样外部还有机会读取结果并销毁协程帧。

如果写成：

```cpp
std::suspend_never final_suspend() noexcept { return {}; }
```

协程结束时可能自动销毁协程帧。
如果外部对象还拿着 handle，再 `destroy()` 就可能出问题。

记住：

> 手写拥有 handle 的 Task / Generator 时，初学阶段优先用 `final_suspend = suspend_always`，由返回对象析构时负责 `destroy()`。

---

## 10. `co_await` 的完整流程

写：

```cpp
auto result = co_await awaitable;
```

编译器会让 awaitable 提供三个操作：

```cpp
bool await_ready();
void await_suspend(std::coroutine_handle<> h);
T await_resume();
```

执行流程：

```text
1. 调 await_ready()
   如果返回 true：不挂起，直接进入 await_resume()
   如果返回 false：准备挂起

2. 调 await_suspend(handle)
   把当前协程 handle 交给 awaiter
   awaiter 可以保存 handle，安排之后恢复

3. 当前协程挂起

4. 某个时刻有人调用 handle.resume()

5. 协程从 co_await 后继续

6. 调 await_resume()
   它的返回值就是 co_await 表达式的结果
```

三个函数的直觉：

| 函数 | 含义 |
| --- | --- |
| `await_ready()` | 是否已经准备好，不需要挂起 |
| `await_suspend(handle)` | 如果要挂起，怎么安排恢复 |
| `await_resume()` | 恢复后给协程什么结果，或者抛什么异常 |

---

## 11. 示例 1：一个不会挂起的 awaitable

这个例子展示 `co_await` 可以返回一个值。

```cpp
#include <coroutine>
#include <exception>
#include <iostream>
#include <utility>

class SimpleTask {
public:
    struct promise_type {
        SimpleTask get_return_object() {
            return SimpleTask{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() { std::terminate(); }
    };

    using Handle = std::coroutine_handle<promise_type>;

    explicit SimpleTask(Handle h) : handle_(h) {}

    SimpleTask(const SimpleTask&) = delete;
    SimpleTask& operator=(const SimpleTask&) = delete;

    SimpleTask(SimpleTask&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~SimpleTask() {
        if (handle_) {
            handle_.destroy();
        }
    }

    bool resume() {
        if (!handle_ || handle_.done()) {
            return false;
        }
        handle_.resume();
        return !handle_.done();
    }

private:
    Handle handle_;
};

struct ReadyValue {
    bool await_ready() const noexcept {
        return true;  // 已经准备好，不挂起
    }

    void await_suspend(std::coroutine_handle<>) const noexcept {
        // await_ready 返回 true，所以不会走到这里
    }

    int await_resume() const noexcept {
        return 42;
    }
};

SimpleTask demo() {
    int value = co_await ReadyValue{};
    std::cout << "value = " << value << "\n";
    co_return;
}

int main() {
    auto task = demo();  // initial_suspend 挂起，函数体还没执行
    task.resume();      // 开始执行
}
```

输出：

```text
value = 42
```

这个例子里：

* `ReadyValue::await_ready()` 返回 `true`。
* 协程不会挂起。
* `co_await ReadyValue{}` 的结果来自 `await_resume()`。

---

## 12. 示例 2：手动挂起和恢复

这个例子展示 `co_await std::suspend_always{}` 会让协程停下来。

```cpp
#include <coroutine>
#include <exception>
#include <iostream>
#include <utility>

class SimpleTask {
public:
    struct promise_type {
        SimpleTask get_return_object() {
            return SimpleTask{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() { std::terminate(); }
    };

    using Handle = std::coroutine_handle<promise_type>;

    explicit SimpleTask(Handle h) : handle_(h) {}

    SimpleTask(const SimpleTask&) = delete;
    SimpleTask& operator=(const SimpleTask&) = delete;

    SimpleTask(SimpleTask&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~SimpleTask() {
        if (handle_) {
            handle_.destroy();
        }
    }

    bool resume() {
        if (!handle_ || handle_.done()) {
            return false;
        }
        handle_.resume();
        return !handle_.done();
    }

private:
    Handle handle_;
};

SimpleTask two_steps() {
    std::cout << "step 1\n";
    co_await std::suspend_always{};
    std::cout << "step 2\n";
    co_return;
}

int main() {
    auto task = two_steps();

    std::cout << "before first resume\n";
    task.resume();

    std::cout << "before second resume\n";
    task.resume();

    std::cout << "done\n";
}
```

输出：

```text
before first resume
step 1
before second resume
step 2
done
```

理解重点：

* `two_steps()` 被调用时只创建协程，不执行函数体。
* 第一次 `resume()` 执行到 `co_await std::suspend_always{}`，然后挂起。
* 第二次 `resume()` 从挂起点后继续执行。

---

## 13. 示例 3：带返回值的 `Task<int>`

下面这个例子展示 `co_return value` 如何通过 `promise_type::return_value()` 保存结果。

```cpp
#include <coroutine>
#include <exception>
#include <iostream>
#include <optional>
#include <utility>

class IntTask {
public:
    struct promise_type {
        std::optional<int> value;
        std::exception_ptr exception;

        IntTask get_return_object() {
            return IntTask{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }

        void return_value(int v) noexcept {
            value = v;
        }

        void unhandled_exception() {
            exception = std::current_exception();
        }
    };

    using Handle = std::coroutine_handle<promise_type>;

    explicit IntTask(Handle h) : handle_(h) {}

    IntTask(const IntTask&) = delete;
    IntTask& operator=(const IntTask&) = delete;

    IntTask(IntTask&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~IntTask() {
        if (handle_) {
            handle_.destroy();
        }
    }

    int get() {
        while (!handle_.done()) {
            handle_.resume();
        }

        auto& promise = handle_.promise();
        if (promise.exception) {
            std::rethrow_exception(promise.exception);
        }
        return *promise.value;
    }

private:
    Handle handle_;
};

IntTask compute_answer() {
    co_return 40 + 2;
}

int main() {
    auto task = compute_answer();
    std::cout << task.get() << "\n";
}
```

输出：

```text
42
```

这个例子里：

* `co_return 42` 调用 `return_value(42)`。
* 返回值保存在 promise 里。
* `get()` 恢复协程直到完成，然后读取 promise。
* 异常也保存在 promise 里，最后由 `get()` 重新抛出。

注意：

这个 `get()` 是教学用的同步等待。
真实异步框架里通常不会用 `while (!done()) resume()` 硬跑，而是交给事件循环或调度器恢复。

---

## 14. 示例 4：异常传播

协程内部抛出的异常不会自动从协程创建处抛出，它会先进入 `promise_type::unhandled_exception()`。

```cpp
IntTask fail() {
    throw std::runtime_error("bad coroutine");
    co_return 0;
}

int main() {
    try {
        auto task = fail();
        std::cout << task.get() << "\n";
    } catch (const std::exception& e) {
        std::cout << "caught: " << e.what() << "\n";
    }
}
```

输出：

```text
caught: bad coroutine
```

关键点：

* 协程体里的未捕获异常会进入 `unhandled_exception()`。
* 如果要让调用者感知异常，需要在 `get()` 或 `await_resume()` 里重新抛出。
* 这和 `std::future::get()` 抛异常的体验类似。

---

## 15. `co_yield` 和生成器

`co_yield` 适合 lazy sequence。

不用协程时，如果想逐个生成值，往往要自己保存状态：

```cpp
class Range {
public:
    explicit Range(int end) : current_(0), end_(end) {}

    bool next() {
        if (current_ >= end_) {
            return false;
        }
        ++current_;
        return true;
    }

    int value() const {
        return current_ - 1;
    }

private:
    int current_;
    int end_;
};
```

协程写法：

```cpp
Generator range(int end) {
    for (int i = 0; i < end; ++i) {
        co_yield i;
    }
}
```

它更自然，因为循环状态由协程帧保存。

---

## 16. 示例 5：支持 range-for 的 `IntGenerator`

这是一个较完整的教学版 generator。

```cpp
#include <coroutine>
#include <exception>
#include <iostream>
#include <iterator>
#include <utility>

class IntGenerator {
public:
    struct promise_type;
    using Handle = std::coroutine_handle<promise_type>;

    struct promise_type {
        int current = 0;
        std::exception_ptr exception;

        IntGenerator get_return_object() {
            return IntGenerator{Handle::from_promise(*this)};
        }

        std::suspend_always initial_suspend() noexcept {
            return {};
        }

        std::suspend_always final_suspend() noexcept {
            return {};
        }

        std::suspend_always yield_value(int value) noexcept {
            current = value;
            return {};
        }

        void return_void() noexcept {}

        void unhandled_exception() {
            exception = std::current_exception();
        }
    };

    class iterator {
    public:
        iterator() = default;

        explicit iterator(Handle h) : handle_(h) {
            advance();
        }

        iterator& operator++() {
            advance();
            return *this;
        }

        int operator*() const {
            return handle_.promise().current;
        }

        bool operator==(std::default_sentinel_t) const {
            return done_;
        }

    private:
        void advance() {
            if (!handle_ || handle_.done()) {
                done_ = true;
                return;
            }

            handle_.resume();
            done_ = handle_.done();

            if (done_ && handle_.promise().exception) {
                std::rethrow_exception(handle_.promise().exception);
            }
        }

        Handle handle_{};
        bool done_ = true;
    };

    explicit IntGenerator(Handle h) : handle_(h) {}

    IntGenerator(const IntGenerator&) = delete;
    IntGenerator& operator=(const IntGenerator&) = delete;

    IntGenerator(IntGenerator&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~IntGenerator() {
        if (handle_) {
            handle_.destroy();
        }
    }

    iterator begin() {
        return iterator{handle_};
    }

    std::default_sentinel_t end() {
        return {};
    }

private:
    Handle handle_;
};

IntGenerator range(int begin, int end) {
    for (int i = begin; i < end; ++i) {
        co_yield i;
    }
}

int main() {
    for (int x : range(3, 7)) {
        std::cout << x << "\n";
    }
}
```

输出：

```text
3
4
5
6
```

理解流程：

```text
range(3, 7)
  -> 创建协程帧
  -> initial_suspend 挂起
  -> begin() 中第一次 resume
  -> 执行到 co_yield 3
  -> yield_value 保存 current = 3
  -> suspend_always 挂起
  -> operator* 读取 current
  -> operator++ 再 resume 到下一个 co_yield
```

`co_yield value` 大致等价于：

```cpp
co_await promise.yield_value(value);
```

---

## 17. `await_suspend` 的返回值

`await_suspend()` 可以有几种返回类型。

### 17.1 返回 `void`

```cpp
void await_suspend(std::coroutine_handle<> h);
```

表示当前协程会挂起，恢复由 awaiter 自己安排。

### 17.2 返回 `bool`

```cpp
bool await_suspend(std::coroutine_handle<> h);
```

* 返回 `true`：当前协程挂起。
* 返回 `false`：当前协程不挂起，继续执行。

### 17.3 返回另一个 coroutine_handle

```cpp
std::coroutine_handle<> await_suspend(std::coroutine_handle<> h);
```

表示恢复另一个协程，这叫 symmetric transfer。
这是实现高性能 task 链接时会用到的高级技巧。

初学阶段先记住：

> 大部分 awaiter 返回 `void` 就够理解了；高级 Task 框架才会大量用 handle 返回值优化恢复链。

---

## 18. 示例 6：一个简单调度器

协程本身不决定在哪恢复。
下面用一个简单队列模拟调度器。

```cpp
#include <coroutine>
#include <exception>
#include <iostream>
#include <queue>
#include <utility>

class Scheduler {
public:
    void schedule(std::coroutine_handle<> h) {
        ready_.push(h);
    }

    void run() {
        while (!ready_.empty()) {
            auto h = ready_.front();
            ready_.pop();

            if (!h.done()) {
                h.resume();
            }
        }
    }

    struct SwitchAwaiter {
        Scheduler& scheduler;

        bool await_ready() const noexcept {
            return false;
        }

        void await_suspend(std::coroutine_handle<> h) const {
            scheduler.schedule(h);
        }

        void await_resume() const noexcept {}
    };

    SwitchAwaiter switch_to() {
        return SwitchAwaiter{*this};
    }

private:
    std::queue<std::coroutine_handle<>> ready_;
};

class Task {
public:
    struct promise_type {
        Task get_return_object() {
            return Task{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() { std::terminate(); }
    };

    using Handle = std::coroutine_handle<promise_type>;

    explicit Task(Handle h) : handle_(h) {}

    Task(const Task&) = delete;
    Task& operator=(const Task&) = delete;

    Task(Task&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~Task() {
        if (handle_) {
            handle_.destroy();
        }
    }

    void start(Scheduler& scheduler) {
        scheduler.schedule(handle_);
    }

private:
    Handle handle_;
};

Task job(Scheduler& scheduler, int id) {
    std::cout << "job " << id << ": step 1\n";
    co_await scheduler.switch_to();

    std::cout << "job " << id << ": step 2\n";
    co_await scheduler.switch_to();

    std::cout << "job " << id << ": done\n";
}

int main() {
    Scheduler scheduler;

    auto a = job(scheduler, 1);
    auto b = job(scheduler, 2);

    a.start(scheduler);
    b.start(scheduler);

    scheduler.run();
}
```

可能输出：

```text
job 1: step 1
job 2: step 1
job 1: step 2
job 2: step 2
job 1: done
job 2: done
```

这个例子说明：

* `co_await scheduler.switch_to()` 把当前协程重新放回 ready 队列。
* 调度器决定下一次恢复谁。
* 协程本身没有创建线程。
* 所有代码仍然在调用 `scheduler.run()` 的那条线程执行。

工程重点：

> 真正决定恢复时机和恢复线程的是 awaiter / scheduler / event loop，不是 `co_await` 关键字本身。

---

## 19. 示例 7：一个玩具版 sleep awaiter

下面示例用新线程模拟异步定时器。
它适合理解机制，但不是生产写法。

```cpp
#include <chrono>
#include <coroutine>
#include <exception>
#include <iostream>
#include <thread>
#include <utility>

using namespace std::chrono_literals;

class Task {
public:
    struct promise_type {
        Task get_return_object() {
            return Task{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() { std::terminate(); }
    };

    using Handle = std::coroutine_handle<promise_type>;

    explicit Task(Handle h) : handle_(h) {}

    Task(const Task&) = delete;
    Task& operator=(const Task&) = delete;

    Task(Task&& other) noexcept
        : handle_(std::exchange(other.handle_, {})) {}

    ~Task() {
        if (handle_) {
            handle_.destroy();
        }
    }

    void start() {
        if (handle_ && !handle_.done()) {
            handle_.resume();
        }
    }

private:
    Handle handle_;
};

struct SleepAwaiter {
    std::chrono::milliseconds delay;

    bool await_ready() const noexcept {
        return delay.count() <= 0;
    }

    void await_suspend(std::coroutine_handle<> h) const {
        std::thread([h, delay = delay] {
            std::this_thread::sleep_for(delay);
            h.resume();
        }).detach();
    }

    void await_resume() const noexcept {}
};

Task demo_sleep() {
    std::cout << "before sleep\n";
    co_await SleepAwaiter{500ms};
    std::cout << "after sleep\n";
}

int main() {
    auto task = demo_sleep();
    task.start();

    // 教学示例：保证 task 活到后台线程 resume 之后。
    std::this_thread::sleep_for(1s);
}
```

输出：

```text
before sleep
after sleep
```

这个例子的风险：

* `detach()` 线程不受管理。
* 如果 `task` 在后台线程 `resume()` 前析构，handle 会悬空。
* 真实项目应该用事件循环、线程池、定时器队列管理恢复。

所以它只适合理解：

```text
await_suspend 保存 handle
异步事件完成后调用 handle.resume()
```

---

## 20. 回调如何变成 `co_await`

很多异步库本来是回调风格：

```cpp
async_read(socket, buffer, [](Error ec, std::size_t n) {
    ...
});
```

协程适配的核心是写一个 awaiter：

```cpp
struct ReadAwaiter {
    Socket& socket;
    Buffer& buffer;
    Error ec;
    std::size_t bytes = 0;

    bool await_ready() const noexcept {
        return false;
    }

    void await_suspend(std::coroutine_handle<> h) {
        async_read(socket, buffer, [this, h](Error e, std::size_t n) mutable {
            ec = e;
            bytes = n;
            h.resume();
        });
    }

    std::size_t await_resume() {
        if (ec) {
            throw std::runtime_error("read failed");
        }
        return bytes;
    }
};
```

使用时：

```cpp
Task<void> session(Socket& socket) {
    Buffer buffer;
    std::size_t n = co_await ReadAwaiter{socket, buffer};
    process(buffer, n);
}
```

真正工程实现会更复杂：

* awaiter 生命周期不能悬空。
* 回调可能在别的线程触发。
* socket 关闭时要恢复协程并返回错误。
* 取消时要 unregister callback。
* 异常要从 `await_resume()` 抛出或返回 `expected`。

但核心思路就是：

```text
回调完成 -> 保存结果 -> resume 协程 -> await_resume 返回结果
```

---

## 21. 协程和异步 I/O 的关系

协程不是异步 I/O 本身。

异步 I/O 需要：

* 操作系统 I/O 能力，例如 epoll、io_uring、IOCP。
* 事件循环。
* 回调或 completion queue。
* 调度器。
* 资源生命周期管理。

协程提供的是表达方式：

```cpp
auto data = co_await socket.async_read();
co_await socket.async_write(data);
```

真正不阻塞线程的是：

* `socket.async_read()` 里的 I/O 实现。
* awaiter 在 `await_suspend()` 里把 handle 交给事件循环。
* 事件完成时事件循环调用 `resume()`。

所以面试里可以这样讲：

> C++20 协程本身只是语言机制，不自带事件循环。它能把异步 I/O 写成顺序代码，但非阻塞能力来自底层 I/O 框架，比如 ASIO、libuv、io_uring 或自研 event loop。

---

## 22. 协程的生命周期

协程生命周期大致是：

```text
调用协程函数
  -> 分配协程帧
  -> 构造 promise
  -> get_return_object()
  -> initial_suspend()
  -> 执行函数体
  -> 遇到 co_await / co_yield 挂起
  -> 被 resume 恢复
  -> co_return 或异常结束
  -> final_suspend()
  -> 外部 destroy()
```

关键问题：

* 谁拥有协程帧？
* 谁负责 `destroy()`？
* 协程挂起后，捕获的引用是否还活着？
* 协程完成后，结果保存在什么地方？
* 如果没人恢复，协程帧会不会泄漏？

手写 Task 时，通常让返回对象 RAII 管理 handle：

```cpp
~Task() {
    if (handle_) {
        handle_.destroy();
    }
}
```

但要注意：

> 如果协程 handle 已经交给调度器或后台线程，Task 析构时直接 destroy 可能让调度器里保存的 handle 变成悬空指针。

这也是协程工程难点之一。

---

## 23. 引用捕获为什么危险

协程可能挂起很久，所以引用生命周期很容易出错。

危险例子：

```cpp
Task<void> bad() {
    std::string s = "hello";

    auto lambda = [&]() -> Task<void> {
        co_await std::suspend_always{};
        std::cout << s << "\n";  // s 可能已经没了
    };

    auto task = lambda();
}
```

更常见的危险：

```cpp
Task<void> use_ref(const std::string& name) {
    co_await async_wait();
    std::cout << name << "\n";  // 调用者传入的对象可能已经销毁
}
```

更安全的写法：

```cpp
Task<void> use_value(std::string name) {
    co_await async_wait();
    std::cout << name << "\n";
}
```

经验：

* 跨挂起点使用的数据，优先值语义。
* 如果必须共享，用 `std::shared_ptr` 或明确的所有权模型。
* 不要把临时对象引用传进可能挂起的协程。

---

## 24. 取消：协程不会自动停止

C++20 协程本身没有内建取消机制。

取消通常由运行时或业务协议提供，例如：

* `std::stop_token`
* 自定义 `CancellationToken`
* socket 关闭
* timeout
* 任务状态标记

示例：

```cpp
#include <coroutine>
#include <iostream>
#include <stop_token>

Task worker(std::stop_token st, Scheduler& scheduler) {
    while (!st.stop_requested()) {
        std::cout << "tick\n";
        co_await scheduler.switch_to();
    }

    std::cout << "cancelled\n";
}
```

取消要点：

* 取消是协作式的。
* 协程需要在合适位置检查。
* 正在等待 I/O 时，要让底层 I/O 也能取消。
* 取消后仍然要保证协程被恢复到一个能清理资源的位置。

最危险的情况：

```text
外部说取消了
但 awaiter 永远不 resume
协程帧里的资源永远不释放
```

---

## 25. `Task`、`future`、线程池的区别

| 概念 | 作用 |
| --- | --- |
| `std::future` | 获取异步结果的同步抽象 |
| 线程池 | 提供并行执行资源 |
| 协程 `Task` | 表达可暂停的异步流程 |
| event loop | 决定异步事件何时恢复协程 |

协程不等于线程池。

你可以有：

```text
协程 + 单线程事件循环
协程 + 多线程事件循环
协程 + 线程池
协程 + I/O completion queue
```

一个典型网络服务可能是：

```text
epoll/io_uring 等 I/O 事件
  -> event loop 收到完成事件
  -> 找到 coroutine_handle
  -> resume 对应协程
  -> 协程继续处理请求
```

---

## 26. `std::suspend_always` 和 `std::suspend_never`

这两个是标准库提供的最简单 awaiter。

`std::suspend_always`：

```cpp
struct suspend_always {
    bool await_ready() const noexcept { return false; }
    void await_suspend(std::coroutine_handle<>) const noexcept {}
    void await_resume() const noexcept {}
};
```

永远挂起。

`std::suspend_never`：

```cpp
struct suspend_never {
    bool await_ready() const noexcept { return true; }
    void await_suspend(std::coroutine_handle<>) const noexcept {}
    void await_resume() const noexcept {}
};
```

永远不挂起。

常见用途：

* 教学示例。
* 控制 `initial_suspend` 和 `final_suspend`。
* 写最小协程返回类型。

---

## 27. `await_transform` 是什么

`promise_type` 可以定义 `await_transform()` 来改写协程内部的 `co_await` 行为。

例如：

```cpp
struct promise_type {
    auto await_transform(SomeType x) {
        return make_awaiter(x);
    }
};
```

当协程里写：

```cpp
co_await something;
```

编译器可能会先调用：

```cpp
promise.await_transform(something)
```

用途：

* 给某个 Task 类型统一注入调度器。
* 限制协程里只能 await 特定类型。
* 把业务对象自动转换成 awaiter。

初学阶段可以先不写它，但要知道很多协程框架会用它做封装。

---

## 28. 性能直觉

协程的性能优势来自：

* 不需要每个任务一个线程。
* 避免大量线程阻塞。
* 控制流由状态机恢复，适合高并发 I/O。
* 栈空间比线程小得多。

但协程也有成本：

* 协程帧分配。
* 间接调用 `resume()`。
* 状态机代码复杂。
* 调度器和 awaiter 的实现成本。
* 跨线程恢复时仍然有同步成本。

性能优化方向：

* 减少不必要的挂起点。
* 减少协程帧里的大对象。
* 避免跨挂起点保存大临时对象。
* 用对象池或自定义 allocator 优化协程帧分配。
* 让恢复尽量发生在合适的执行器上，减少线程跳转。

---

## 29. 工程用途

### 29.1 异步 I/O

最典型。

适合：

* 网络服务器。
* 数据库异步客户端。
* RPC 客户端。
* 文件异步读写。

### 29.2 Generator

适合：

* lazy sequence。
* parser。
* pipeline。
* 按需遍历大数据。

### 29.3 Actor / 任务系统

适合表达：

* 等消息。
* 等 timeout。
* 等某个任务完成。
* 多阶段状态机。

### 29.4 游戏和仿真流程

例如：

```cpp
Task<void> play_cutscene() {
    show_dialog("Hello");
    co_await wait_seconds(2);
    move_camera();
    co_await wait_animation_done();
    spawn_enemy();
}
```

协程能把时间序列行为写得比较自然。

---

## 30. 常见坑

### 30.1 把协程当轻量线程

协程不会自动并行，也不会自动调度到别的线程。

### 30.2 不知道谁负责 `resume()`

看到 `co_await`，必须追问：

```text
await_suspend 里把 handle 交给谁？
谁会在未来调用 resume？
在哪条线程调用？
如果失败了还会不会 resume？
```

### 30.3 `final_suspend` 用错

如果返回对象持有 handle，`final_suspend` 通常不要随便用 `suspend_never`。

### 30.4 协程帧泄漏

创建了协程，但没人 `destroy()`。

### 30.5 悬空引用

跨挂起点使用引用、指针、lambda 捕获都要特别谨慎。

### 30.6 异常吞掉

`unhandled_exception()` 只是捕获异常。
如果不在 `get()` 或 `await_resume()` 里重新抛，调用方可能完全不知道失败了。

### 30.7 取消后不恢复

取消不是直接销毁协程。
很多资源清理逻辑仍然依赖协程继续执行到清理路径。

### 30.8 awaiter 生命周期不对

如果回调里保存了 `this`，但 awaiter 已经被销毁，就会出问题。
真实异步适配器必须仔细设计 awaiter 的生命周期。

---

## 31. 面试怎么讲 C++20 协程

如果面试官问“C++20 协程是什么”，可以回答：

> C++20 协程是一种语言级可挂起函数机制。函数里出现 `co_await`、`co_return` 或 `co_yield` 后，编译器会把它改写成状态机，并把跨挂起点的局部变量保存在协程帧里。它不是线程，不会自动并行；真正决定什么时候恢复、在哪个线程恢复的是 awaitable、调度器或事件循环。

如果问“`co_await` 做了什么”，可以回答：

> `co_await` 会把对象转换成 awaiter，然后依次调用 `await_ready()`、`await_suspend(handle)`、`await_resume()`。`await_ready()` 决定是否需要挂起，`await_suspend()` 拿到当前协程句柄并安排未来恢复，`await_resume()` 在恢复后返回结果或抛异常。

如果问“`promise_type` 是什么”，可以回答：

> `promise_type` 是协程返回类型和编译器生成状态机之间的协议对象。它定义协程返回对象如何创建，初始和最终是否挂起，`co_return` 如何保存返回值，异常如何处理，`co_yield` 如何产出值。

如果问“协程难点是什么”，可以回答：

> 语法不难，难点是工程边界：协程帧生命周期谁管理、handle 谁持有、什么时候 resume、在哪条线程 resume、异常怎么传播、取消怎么处理，以及跨挂起点的引用是否安全。

---

## 32. 学习路线

建议按这个顺序学：

1. 理解协程不是线程。
2. 理解协程会被编译器改写成状态机。
3. 掌握 `co_await` 的三件套。
4. 手写最小 `Task<void>`。
5. 手写 `Task<int>`，理解返回值和异常。
6. 手写 `Generator`，理解 `co_yield`。
7. 写一个简单调度器，理解谁调用 `resume()`。
8. 写一个 sleep awaiter，理解异步完成后恢复。
9. 再看 ASIO、libunifex、cppcoro、Drogon 协程等框架。
10. 最后再研究 symmetric transfer、allocator、自定义调度器和取消。

---

## 33. 一页总结

协程最重要的理解链：

```text
协程函数
  -> 编译器生成状态机
  -> 状态保存在协程帧
  -> promise_type 定义协程协议
  -> co_await 通过 awaiter 挂起和恢复
  -> coroutine_handle 控制 resume/destroy
  -> 调度器/事件循环决定恢复时机和线程
```

最重要的 4 句话：

1. 协程不是线程，而是可挂起函数。
2. `co_await` 不是魔法，本质是 `await_ready / await_suspend / await_resume` 协议。
3. `promise_type` 是协程返回对象和编译器之间的约定。
4. 真实工程难点在生命周期、调度、异常、取消和线程安全。

如果只记一句：

> C++20 协程的价值是把异步流程写直，而不是把并发问题自动解决掉。

---

## 34. 参考方向

可以继续看：

* C++ reference: coroutine support
* cppcoro：协程工具库，适合看 generator/task 设计
* Boost.Asio / standalone Asio：网络异步和协程结合
* Drogon coroutine：Web 框架中的协程实践
* libunifex / stdexec：异步模型和 sender/receiver 方向

---

# [11]现代C++常用工具类型

# 现代 C++ 常用工具类型

时间：2026/04/09

> 关键词：`optional`、`variant`、`any`、`string_view`、`span`、`expected`  
> 核心目标：掌握几个现代 C++ 里非常高频、能直接改善接口表达和代码质量的标准库类型。

---

## 1. 为什么这些类型重要

现代 C++ 的很多进步，不只在语法，还在于：

* 用更明确的类型表达意图

比如：

* “可能没有值”
* “可能是多种类型之一”
* “只读字符串视图”
* “一段连续内存视图”

这些都不该继续靠：

* `nullptr`
* 魔法值
* `void*`
* 裸指针 + 长度

来硬撑。

---

## 2. `std::optional<T>`：可能有，也可能没有

```cpp
#include <optional>

std::optional<int> find_id();
```

它适合表达：

* 成功返回一个值
* 失败时没有值

比“返回 `-1` 表示失败”更清晰。

常用接口：

* `has_value()`
* `value()`
* `value_or(default)`

---

## 3. `std::variant`：类型安全的联合体

```cpp
#include <variant>

std::variant<int, std::string> v;
```

它表示：

* 值一定是若干候选类型中的一个

相比传统 `union`，它：

* 类型安全
* 自动管理对象生命周期

配合 `std::visit` 很常见。

---

## 4. `std::any`：完全动态类型

```cpp
#include <any>

std::any x = 42;
x = std::string("hello");
```

它适合：

* 真正不知道运行期会是什么类型

但代价是：

* 类型信息晚到运行期
* 可读性和性能都不如 `variant`

经验上：

* 能用 `variant` 就不要先上 `any`

---

## 5. `std::string_view`：无拷贝字符串视图

```cpp
#include <string_view>

void print(std::string_view s);
```

优点：

* 不拥有字符串
* 不分配内存
* 可接 `std::string`、字面量、子串视图

风险：

* 它不延长底层字符串生命周期

所以不能把它保存得比源字符串活得更久。

---

## 6. `std::span<T>`：无拷贝连续内存视图

```cpp
#include <span>

void process(std::span<const int> xs);
```

适合：

* 数组
* `std::vector`
* `std::array`

相比传：

* 裸指针 + 长度

更清晰，也更安全。

---

## 7. `std::expected`：值或错误

如果你的环境支持 C++23，可以关注：

```cpp
std::expected<Value, Error>
```

它适合表达：

* 成功时返回值
* 失败时返回明确错误信息

相比 `optional`，它多了：

* 为什么失败

---

## 8. 这些类型最核心的接口收益

### 8.1 `optional`

不再靠魔法值表示“没有结果”。

### 8.2 `variant`

不再靠手写 tag + union。

### 8.3 `string_view`

函数参数更轻、更泛化。

### 8.4 `span`

数组接口更现代。

---

## 9. 常见坑

### 9.1 `string_view` / `span` 生命周期错误

它们都只是视图，不拥有数据。

### 9.2 用 `any` 代替清晰设计

很多时候 `any` 只是把类型问题往后拖。

### 9.3 `optional` 里塞重对象却频繁拷贝

虽然语义清晰，但也要注意值类别和性能。

---

## 10. 一页总结

这几个类型的价值可以压缩成一句话：

> 用更准确的标准库类型表达接口语义，减少魔法值、裸指针和不透明约定。

最值得优先掌握的顺序通常是：

1. `optional`
2. `string_view`
3. `span`
4. `variant`
5. `any`
6. `expected`

---

# [12]ranges与views

# ranges 与 views

时间：2026/04/09

> 关键词：`std::ranges`、`std::views`、惰性求值、管道风格、projection、view、dangling  
> 核心目标：理解 ranges 为什么不是“语法糖”，以及 views 在工程里到底解决了什么问题。

---

## 1. 为什么会有 ranges

传统 STL 算法常见写法是：

```cpp
std::sort(v.begin(), v.end());
auto it = std::find_if(v.begin(), v.end(), pred);
```

它的问题不是不能用，而是：

* `begin/end` 很机械
* 容器、区间、子区间表达不统一
* 组合多步处理时可读性一般

`std::ranges` 的目标是：

* 直接面向“区间”编程
* 让算法和数据视图更自然地组合

---

## 2. 什么是 range

可以先粗略理解成：

> 一个可以拿到 `begin` 和 `end` 的可遍历对象。

例如：

* `std::vector`
* `std::array`
* `std::string`
* 某些 view

所以 `ranges` 的核心不是新容器，而是：

* 一套更统一的区间抽象

---

## 3. ranges 算法和传统算法的区别

传统写法：

```cpp
std::sort(v.begin(), v.end());
```

ranges 写法：

```cpp
std::ranges::sort(v);
```

优点：

* 少写重复样板
* 更容易配合子区间和 view
* 接口更贴近“处理一段范围”这件事

---

## 4. views 是什么

`view` 可以先理解成：

> 一个轻量、通常不拥有数据、按需计算的区间视图。

它最重要的特性通常是：

* 不拷贝底层数据
* 惰性求值
* 可组合

例如：

```cpp
auto even = v | std::views::filter([](int x) { return x % 2 == 0; });
```

这里并没有立刻生成一个新容器。

---

## 5. 为什么 views 很有价值

如果没有 views，很多处理中间会写成：

* 先过滤到一个新 vector
* 再 transform 到另一个新 vector
* 再截取前几个元素

这样的问题是：

* 中间容器多
* 拷贝和分配多
* 代码意图被“存中间结果”打断

views 的思路是：

* 先把处理流程串起来
* 真正遍历时再逐步应用

---

## 6. 最常见的 view 适配器

### 6.1 `filter`

```cpp
auto even = v | std::views::filter([](int x) { return x % 2 == 0; });
```

### 6.2 `transform`

```cpp
auto sq = v | std::views::transform([](int x) { return x * x; });
```

### 6.3 `take`

```cpp
auto first3 = v | std::views::take(3);
```

### 6.4 `drop`

```cpp
auto tail = v | std::views::drop(5);
```

### 6.5 `keys` / `values`

```cpp
auto ks = mp | std::views::keys;
auto vs = mp | std::views::values;
```

---

## 7. 管道风格最直观的例子

```cpp
#include <ranges>
#include <vector>
#include <iostream>

int main() {
    std::vector<int> v = {1, 2, 3, 4, 5, 6, 7, 8};

    auto result = v
        | std::views::filter([](int x) { return x % 2 == 0; })
        | std::views::transform([](int x) { return x * x; })
        | std::views::take(2);

    for (int x : result) {
        std::cout << x << '\n';
    }
}
```

---

## 8. views 的一个关键点：惰性

下面这句：

```cpp
auto result = v | std::views::filter(pred);
```

通常不会立刻把所有元素筛一遍。  
真正发生计算，往往是在你：

* 遍历它
* 构造新容器
* 调用需要实际消费元素的算法

所以 `view` 更像“处理规则的组合”，不是立即产出的结果集。

---

## 9. view 和容器的区别

容器更像：

* 真正拥有数据
* 独立存储结果

view 更像：

* 一层观察或变换
* 常常依赖底层对象继续存在

这一点直接影响生命周期安全。

---

## 10. 什么时候需要把 view 落地成容器

如果你需要：

* 持久保存结果
* 随机访问结果
* 与不支持 ranges 的旧接口交互

就需要把 view materialize 成容器。

常见方式：

```cpp
std::vector<int> out(std::ranges::begin(view), std::ranges::end(view));
```

如果是 C++23，还常见：

```cpp
auto out = view | std::ranges::to<std::vector>();
```

---

## 11. `projection`：ranges 里非常实用但经常被忽略的点

很多 ranges 算法支持 projection。  
意思是：

* 比较或匹配前，先对元素投影出某个字段

例如按成员排序：

```cpp
struct User {
    int id;
    std::string name;
};

std::ranges::sort(users, {}, &User::id);
```

这在工程里很实用。

---

## 12. 常见算法示例

```cpp
auto it = std::ranges::find(v, 42);
std::ranges::sort(v);
bool ok = std::ranges::all_of(v, pred);
std::ranges::copy(v, std::back_inserter(out));
```

---

## 13. 生命周期问题：views 最大的坑之一

因为很多 view 不拥有数据，所以要小心底层对象生命周期。

危险例子：

```cpp
auto make_view() {
    std::vector<int> v = {1, 2, 3};
    return v | std::views::filter([](int x) { return x > 1; }); // 危险
}
```

所以要记住：

* view 很轻，但通常不负责延长底层容器生命周期

---

## 14. 常见坑

### 14.1 把 view 当拥有结果的容器

它通常不是。

### 14.2 底层容器变了，view 却还在继续用

例如容器被销毁、扩容、失效。

### 14.3 pipeline 过长且带副作用

会让调试和推理变难。

### 14.4 误以为 ranges 一定更快

语义更清晰不代表每个场景都自动最优。

---

## 15. 一页总结

ranges 与 views 最重要的理解链是：

1. ranges 让算法直接面向区间
2. views 提供不拥有数据、可组合、惰性的处理视图
3. 它们最擅长表达“数据处理流水线”
4. 真正要注意的是生命周期、materialize 时机和可读性边界

如果只记一句：

> view 更像“处理规则”，容器才是“真正结果”。

---

# [13]错误处理与expected、异常设计

# 错误处理与 `expected`、异常设计

时间：2026/04/09

> 关键词：异常、`noexcept`、`std::expected`、`optional`、错误传播、恢复性错误、编程错误  
> 核心目标：建立一套工程上可执行的判断标准，知道什么时候该抛异常，什么时候该返回错误值或 `expected`。

---

## 1. 错误处理不是“选一个 API”那么简单

错误处理真正要先回答的是：

* 这是不是预期内会发生的失败
* 调用方是否应该恢复
* 失败信息需要多详细
* 代码库是否接受异常

所以讨论异常和 `expected` 时，重点不是站队，而是：

* 哪种语义更适合这一层接口

---

## 2. 先把失败分类型

最有用的分类通常是：

### 2.1 编程错误 / 违反前置条件

例如：

* 越界
* 非法状态
* 不满足接口约束

这类错误通常不属于“正常业务失败”。

### 2.2 可恢复的业务失败

例如：

* 解析失败
* 文件不存在
* 权限不足
* 网络超时

调用方通常有机会决定下一步怎么做。

### 2.3 致命错误

例如：

* 系统资源耗尽
* 程序已进入不一致状态

---

## 3. 异常适合什么场景

异常最适合：

* 错误很少发生
* 一旦发生，需要沿调用栈自动展开
* 局部函数不适合层层手动返回错误码

典型例子：

* 构造函数失败
* 资源获取失败
* 深层调用链中的异常退出

---

## 4. `expected` 适合什么场景

`std::expected<T, E>` 更适合：

* 失败是正常、可预期分支
* 调用方需要显式处理失败
* 你希望错误成为接口类型的一部分

例如：

* 配置解析
* 用户输入校验
* 业务规则检查
* 网络协议解析

---

## 5. `optional` 和 `expected` 的区别

`optional<T>` 表示：

* 可能有值，也可能没值

但它不告诉你：

* 为什么没值

`expected<T, E>` 表示：

* 要么有 `T`
* 要么有错误 `E`

所以经验上：

* 只有“有没有结果”时，用 `optional`
* 需要表达“为什么失败”时，用 `expected`

---

## 6. 一个最直接的例子

```cpp
std::optional<User> find_user(int id);
std::expected<User, ParseError> parse_user(std::string_view text);
```

前者表达“可能没有”，后者表达“失败且要知道原因”。

---

## 7. 什么时候不适合抛异常

### 7.1 失败是高频正常分支

### 7.2 热路径里非常在意开销和可预测性

### 7.3 跨 ABI / 跨模块边界不方便统一异常策略

### 7.4 团队整体约束就是禁用异常

这时更适合：

* `expected`
* error code
* status object

---

## 8. 什么时候异常特别合理

### 8.1 构造函数失败

### 8.2 无法在每层都写样板检查

### 8.3 资源清理由 RAII 承担

异常和 RAII 配合得最好：

* 抛出异常
* 栈展开
* 局部资源自动释放

---

## 9. 一个 `expected` 风格的例子

```cpp
#include <expected>
#include <string_view>

enum class ParseError {
    Empty,
    InvalidNumber
};

std::expected<int, ParseError> parse_int(std::string_view s) {
    if (s.empty()) {
        return std::unexpected(ParseError::Empty);
    }
    int value = 0;
    for (char ch : s) {
        if (ch < '0' || ch > '9') {
            return std::unexpected(ParseError::InvalidNumber);
        }
        value = value * 10 + (ch - '0');
    }
    return value;
}
```

---

## 10. 异常风格的例子

```cpp
int parse_int_or_throw(std::string_view s) {
    if (s.empty()) throw std::invalid_argument("empty");
    int value = 0;
    for (char ch : s) {
        if (ch < '0' || ch > '9') {
            throw std::invalid_argument("invalid number");
        }
        value = value * 10 + (ch - '0');
    }
    return value;
}
```

---

## 11. 一层系统里最好统一风格

最容易出问题的是混乱：

* 一半函数抛异常
* 一半函数返回错误码
* 一半函数返回空值

更稳妥的做法是：

* 每一层接口尽量有统一错误处理约定

---

## 12. `noexcept` 的意义

`noexcept` 表示：

* 这个函数承诺不抛异常

它既是语义约束，也会影响某些容器对移动操作的选择。

---

## 13. 析构函数为什么通常不能抛

析构阶段如果异常继续外逃，尤其在栈展开过程中，会很危险。  
工程上通常遵循：

* 析构函数不要让异常逃出

---

## 14. 一个很实用的决策表

### 14.1 用异常

当失败：

* 不常发生
* 不适合做常规分支
* 需要栈展开自动清理

### 14.2 用 `expected`

当失败：

* 很常见
* 需要显式处理
* 希望错误成为接口类型的一部分

### 14.3 用 `optional`

当失败：

* 只是“没有结果”
* 不需要详细错误原因

---

## 15. 常见坑

### 15.1 用异常做普通循环分支

### 15.2 用 `optional` 隐藏真实错误信息

### 15.3 一个模块里混用三四种错误风格

### 15.4 给所有函数乱加 `noexcept`

---

## 16. 参考实例：`expected` 风格解析配置

当失败是正常分支，并且调用方需要知道原因时，可以把错误写进返回类型。

```cpp
#include <expected>
#include <charconv>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

enum class ParseError {
    empty,
    invalid_number,
    out_of_range,
};

std::expected<int, ParseError> parse_port(std::string_view text) {
    if (text.empty()) {
        return std::unexpected(ParseError::empty);
    }

    int value = 0;
    const char* first = text.data();
    const char* last = text.data() + text.size();

    auto [ptr, ec] = std::from_chars(first, last, value);
    if (ec != std::errc{} || ptr != last) {
        return std::unexpected(ParseError::invalid_number);
    }

    if (value <= 0 || value > 65535) {
        return std::unexpected(ParseError::out_of_range);
    }

    return value;
}

void load_endpoint(std::string_view port_text) {
    auto port = parse_port(port_text);
    if (!port) {
        report_parse_error(port.error());
        return;
    }

    connect_to_port(*port);
}
```

同样的场景如果用异常，适合“失败少见、希望跨多层传播”的边界：

```cpp
int parse_port_or_throw(std::string_view text) {
    auto port = parse_port(text);
    if (!port) {
        throw std::runtime_error("invalid port");
    }
    return *port;
}
```

选择标准仍然是：

* 高频可恢复失败：`expected`
* 不常发生、跨层传播失败：异常
* 只是没有值且不关心原因：`optional`

---

## 17. 一页总结

错误处理最重要的不是“异常 vs `expected` 谁更先进”，而是：

1. 先判断失败是不是正常可恢复分支
2. 再决定错误是否应该进入类型系统
3. 再决定是否需要异常自动展开调用栈

可以直接记这条经验：

* 不常发生、跨层传播、依赖 RAII 清理：优先考虑异常
* 常见失败、需要显式处理、想把错误写进接口：优先考虑 `expected`

如果只记一句：

> 错误处理风格最怕的不是选错，而是同一层接口没有一致性。

---

# [14]内存泄漏检测与管理

# 内存泄漏检测与管理

时间：2026/04/16

> 关键词：RAII、`unique_ptr`、`shared_ptr` 循环引用、Sanitizer、Valgrind、资源封装  
> 核心目标：把“谁释放、何时释放、怎么定位泄漏”变成工程上可检查的规则。

---

## 1. 什么才叫内存泄漏

最典型的内存泄漏是：

* 一块堆内存已经没有任何有效路径再访问它
* 但它也永远不会被释放

例如：

```cpp
void bad() {
    int* p = new int(42);
}
```

函数结束后，`p` 没了，这块内存也没人能再 `delete`。  
这就是最标准的泄漏。

但工程里还要区分另一类问题：

* 对象严格来说还“可达”
* 但长期不释放，内存占用持续上涨

这未必是严格意义上的 leak，但同样会把服务拖垮。

---

## 2. 最常见的泄漏来源

### 2.1 裸 `new` / `delete` 配对失败

最常见的问题不是“不会 `delete`”，而是：

* 提前 `return`
* 中途 `throw`
* 多分支路径漏掉释放

### 2.2 容器里放 owning raw pointer

```cpp
std::vector<Foo*> items;
items.push_back(new Foo());
```

这种写法会把“谁来删”变成记忆题。

### 2.3 `shared_ptr` 循环引用

两个对象互相持有 `shared_ptr`，引用计数永远不会归零。

### 2.4 C 风格资源没及时封装

比如：

* `FILE*`
* `malloc/free`
* socket / fd
* 第三方库句柄

如果它们在业务代码里裸奔，后面很容易漏掉释放。

---

## 3. 第一原则：先别写出会泄漏的代码

现代 C++ 管理泄漏，重点不是“人工记得回收”，而是默认采用不容易泄漏的结构。

优先顺序通常是：

1. 能值语义就值语义
2. 能栈对象就栈对象
3. 必须动态分配时优先 `std::unique_ptr`
4. 确实需要共享拥有时才用 `std::shared_ptr`
5. 裸指针和引用默认只表达观察，不表达拥有

这背后的核心思想就是 RAII：

* 对象析构时自动释放资源

只要生命周期跟对象绑在一起，泄漏风险会大幅下降。

---

## 4. 一个典型泄漏例子

错误写法：

```cpp
#include <memory>

struct Widget {};

Widget* create_widget(bool failed) {
    Widget* p = new Widget();
    if (failed) return nullptr; // 泄漏
    return p;
}
```

问题不在 `new` 本身，而在：

* 释放依赖调用路径是否完整

更稳妥的写法：

```cpp
#include <memory>

struct Widget {};

std::unique_ptr<Widget> create_widget(bool failed) {
    auto p = std::make_unique<Widget>();
    if (failed) return nullptr;
    return p;
}
```

这样即使中途提前返回，局部对象也会自动清理。

---

## 5. 智能指针也不是绝对安全

`unique_ptr` 很少造成泄漏，真正容易出问题的是 `shared_ptr`。

```cpp
#include <memory>

struct Node {
    std::shared_ptr<Node> next;
    std::shared_ptr<Node> prev; // 错：可能形成环
};
```

如果两个节点互相持有，引用计数就会卡住。

更常见的修正方式是：

```cpp
#include <memory>

struct Node {
    std::shared_ptr<Node> next;
    std::weak_ptr<Node> prev; // 观察，不拥有
};
```

经验上：

* 形成树状、图状、双向关系时，先主动检查是否存在环
* “回指”通常更适合 `weak_ptr`

---

## 6. 泄漏和“内存一直涨”不是一回事

下面这些情况不一定是严格意义上的 leak：

* 全局缓存只增不减
* `std::vector` / `std::string` 容量长期不回收
* 任务队列积压
* 对象池尺寸只扩不缩

它们的问题是：

* 生命周期策略不合理
* 上限控制缺失

所以排查内存问题时，要先分清两类：

1. 对象已经不可达，但没释放
2. 对象还可达，但系统把它留得太久

前者更像 bug，后者更像管理问题，但两者都要处理。

---

## 7. 怎么检测泄漏

### 7.1 先上 Sanitizer

本地开发最常用的办法通常是编译时打开 Sanitizer：

```bash
clang++ -std=c++20 -g -O1 -fno-omit-frame-pointer -fsanitize=address main.cpp -o app
ASAN_OPTIONS=detect_leaks=1 ./app
```

如果你的工具链把 leak 检测拆开，也可以按需使用：

* `-fsanitize=leak`

它的优点是：

* 定位快
* 栈回溯清楚
* 很适合集成到测试里

### 7.2 再用 Valgrind 看存量问题

```bash
valgrind --leak-check=full --show-leak-kinds=all ./app
```

它更慢，但对一些历史代码排查仍然很有价值。

### 7.3 别只测“正常退出”

很多泄漏只在这些场景出现：

* 异常路径
* 超时取消
* 重试逻辑
* 长时间运行
* 高并发压力

所以测试不能只跑正常路径。

---

## 8. Valgrind 基础应用

Valgrind 是一套动态分析工具，最常用的是：

* `memcheck`：检查内存泄漏、越界访问、使用未初始化内存、重复释放等
* `helgrind`：检查多线程数据竞争、锁使用问题
* `drd`：检查多线程数据竞争和线程 API 使用问题
* `massif`：分析堆内存占用峰值
* `callgrind`：分析函数调用和性能热点

平时排查 C++ 内存问题，先掌握 `memcheck` 就够；涉及多线程再看 `helgrind` 和 `drd`。

注意：

* Valgrind 主要适合 Linux 环境
* macOS 上支持不如 Linux 稳定，尤其新系统和 Apple Silicon 经常不方便
* 如果本机是 macOS，工程实践里更推荐用 Linux 虚拟机、Docker、远程 Linux 机器或 WSL
* Valgrind 会让程序慢很多，通常比原始运行慢几十倍，不适合直接跑线上服务

### 8.1 编译时建议加调试信息

Valgrind 不需要重新编译插桩，但为了看到清楚的源码行号，建议这样编译：

```bash
g++ -std=c++20 -g -O0 -fno-omit-frame-pointer main.cpp -o app
```

参数含义：

* `-g`：保留调试信息，Valgrind 才能显示文件名和行号
* `-O0`：关闭优化，回溯更接近源码
* `-fno-omit-frame-pointer`：保留栈帧信息，回溯更完整

如果项目使用 CMake，可以临时打开 Debug 构建：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
```

### 8.2 Memcheck 查内存泄漏

最常用命令：

```bash
valgrind \
  --tool=memcheck \
  --leak-check=full \
  --show-leak-kinds=all \
  --track-origins=yes \
  --num-callers=30 \
  ./app
```

常用参数：

* `--tool=memcheck`：使用内存检查工具，默认也是它
* `--leak-check=full`：显示每个泄漏点的详细调用栈
* `--show-leak-kinds=all`：显示所有泄漏类型
* `--track-origins=yes`：追踪未初始化值来自哪里，速度更慢但定位更准
* `--num-callers=30`：调用栈显示更多层

如果希望 CI 或脚本根据是否有泄漏返回失败，可以加：

```bash
valgrind \
  --leak-check=full \
  --error-exitcode=1 \
  ./app
```

只要 Valgrind 检测到错误，进程退出码就是 `1`，方便自动化检查。

### 8.3 一个最小泄漏例子

示例代码：

```cpp
#include <iostream>

void leak() {
    int* p = new int[10];
    p[0] = 42;
}

int main() {
    leak();
    std::cout << "done\n";
}
```

编译并运行：

```bash
g++ -std=c++20 -g -O0 leak.cpp -o leak
valgrind --leak-check=full --show-leak-kinds=all ./leak
```

典型输出里会看到类似信息：

```text
HEAP SUMMARY:
    in use at exit: 40 bytes in 1 blocks

40 bytes in 1 blocks are definitely lost
    at 0x...: operator new[](unsigned long)
    by 0x...: leak() (leak.cpp:4)
    by 0x...: main (leak.cpp:9)

LEAK SUMMARY:
    definitely lost: 40 bytes in 1 blocks
```

重点看两处：

* `definitely lost`：明确泄漏，优先修
* 栈回溯：从 `operator new[]` 往下看，找到自己代码里的分配位置

修正方式：

```cpp
#include <iostream>
#include <memory>

void no_leak() {
    auto p = std::make_unique<int[]>(10);
    p[0] = 42;
}

int main() {
    no_leak();
    std::cout << "done\n";
}
```

更推荐从所有权上修掉问题，而不是简单在所有路径上补 `delete[]`。

### 8.4 Valgrind 的泄漏类型怎么看

Valgrind 常见泄漏分类：

| 类型 | 含义 | 优先级 |
| --- | --- | --- |
| `definitely lost` | 已经没有任何指针能指向这块内存，明确泄漏 | 最高 |
| `indirectly lost` | 因为上层对象泄漏，导致它指向的子对象也泄漏 | 高 |
| `possibly lost` | Valgrind 只能找到疑似指针，比如指向内存中间位置 | 中 |
| `still reachable` | 程序退出时仍然有指针能访问，严格说不一定是泄漏 | 低到中 |
| `suppressed` | 被 suppression 规则忽略的报告 | 视情况 |

排查顺序通常是：

1. 先修 `definitely lost`
2. 再看 `indirectly lost`
3. 根据业务判断 `possibly lost`
4. 最后再处理 `still reachable`

`still reachable` 常见于：

* 全局单例
* 进程级缓存
* 第三方库退出时没有显式释放的全局资源
* 日志库、线程池、运行时库内部对象

它不一定要立刻修，但如果服务长期运行内存持续上涨，就不能只因为它是 `still reachable` 就忽略。

### 8.5 Memcheck 不只查泄漏

Memcheck 还能查很多典型内存错误。

#### 越界写

```cpp
int* p = new int[3];
p[3] = 10; // 越界
delete[] p;
```

Valgrind 可能报告：

```text
Invalid write of size 4
```

#### 越界读

```cpp
int* p = new int[3];
int x = p[3]; // 越界
delete[] p;
```

Valgrind 可能报告：

```text
Invalid read of size 4
```

#### Use After Free

```cpp
int* p = new int(42);
delete p;
std::cout << *p << "\n"; // 释放后继续使用
```

Valgrind 可能报告：

```text
Invalid read of size 4
Address ... is 0 bytes inside a block of size 4 free'd
```

#### 重复释放

```cpp
int* p = new int(42);
delete p;
delete p; // double free
```

Valgrind 可能报告：

```text
Invalid free() / delete / delete[] / realloc()
```

#### `new` / `delete[]` 不匹配

```cpp
int* p = new int[10];
delete p; // 错：应该 delete[]
```

Valgrind 可能报告：

```text
Mismatched free() / delete / delete []
```

#### 使用未初始化值

```cpp
int x;
if (x > 0) {
    std::cout << x << "\n";
}
```

Valgrind 可能报告：

```text
Conditional jump or move depends on uninitialised value(s)
```

这种问题建议加 `--track-origins=yes`，否则只知道哪里用了未初始化值，不一定知道它最早从哪里来。

### 8.6 多进程和子进程

如果程序会 `fork` 或启动子进程，可以加：

```bash
valgrind \
  --trace-children=yes \
  --leak-check=full \
  ./app
```

`--trace-children=yes` 会让 Valgrind 继续跟踪子进程。

如果子进程很多，输出会很乱，建议先缩小测试范围，或者给不同进程写不同日志：

```bash
valgrind \
  --trace-children=yes \
  --log-file=valgrind.%p.log \
  ./app
```

其中 `%p` 会替换成进程 ID。

### 8.7 多线程程序能用 Memcheck 吗

能。

Memcheck 可以检查多线程程序里的：

* 泄漏
* 越界访问
* use-after-free
* double free
* 未初始化内存使用

但 Memcheck 不是专门的数据竞争检测器。

也就是说：

```text
多线程程序的内存错误 -> Memcheck 能查一部分
多线程数据竞争 / 锁问题 -> 用 Helgrind 或 DRD
```

### 8.8 Helgrind 查数据竞争

Helgrind 用来检查线程之间是否存在 data race。

典型命令：

```bash
valgrind \
  --tool=helgrind \
  --history-level=full \
  ./app
```

示例代码：

```cpp
#include <thread>

int counter = 0;

void worker() {
    for (int i = 0; i < 100000; ++i) {
        ++counter; // 多线程同时读写，没有同步
    }
}

int main() {
    std::thread t1(worker);
    std::thread t2(worker);
    t1.join();
    t2.join();
}
```

编译时要带 pthread：

```bash
g++ -std=c++20 -g -O0 race.cpp -pthread -o race
valgrind --tool=helgrind ./race
```

典型输出里会看到：

```text
Possible data race during read of size 4
Possible data race during write of size 4
```

核心意思是：

* 至少两个线程访问了同一块内存
* 至少一个访问是写
* Helgrind 没看到足够的同步关系

修正方式之一是加锁：

```cpp
#include <mutex>
#include <thread>

int counter = 0;
std::mutex m;

void worker() {
    for (int i = 0; i < 100000; ++i) {
        std::lock_guard<std::mutex> lock(m);
        ++counter;
    }
}

int main() {
    std::thread t1(worker);
    std::thread t2(worker);
    t1.join();
    t2.join();
}
```

如果只是计数器，也可以用原子变量：

```cpp
#include <atomic>
#include <thread>

std::atomic<int> counter{0};

void worker() {
    for (int i = 0; i < 100000; ++i) {
        counter.fetch_add(1, std::memory_order_relaxed);
    }
}
```

### 8.9 Helgrind 能发现哪些线程问题

Helgrind 常见能发现：

* 读写同一变量但没有锁
* 一个线程写、另一个线程读但没有同步
* 锁顺序不一致，存在潜在死锁风险
* pthread mutex 使用错误
* 条件变量使用不当

例如锁顺序不一致：

```cpp
std::mutex a;
std::mutex b;

void f1() {
    std::lock_guard<std::mutex> l1(a);
    std::lock_guard<std::mutex> l2(b);
}

void f2() {
    std::lock_guard<std::mutex> l1(b);
    std::lock_guard<std::mutex> l2(a);
}
```

`f1` 是先锁 `a` 再锁 `b`，`f2` 是先锁 `b` 再锁 `a`。  
如果两个线程同时执行，就可能互相等待。

修正方式：

```cpp
void safe() {
    std::scoped_lock lock(a, b);
}
```

`std::scoped_lock` 可以一次性锁多个 mutex，避免手写锁顺序。

### 8.10 DRD 查多线程问题

DRD 和 Helgrind 类似，也用于检查多线程程序。

命令：

```bash
valgrind \
  --tool=drd \
  ./app
```

一般经验：

* `helgrind` 对锁顺序、happens-before 分析比较常用
* `drd` 对 pthread 使用问题也比较敏感
* 两者可能报告不同问题
* 多线程疑难问题可以两个都跑一遍

DRD 常见参数：

```bash
valgrind \
  --tool=drd \
  --check-stack-var=yes \
  --exclusive-threshold=100 \
  --shared-threshold=100 \
  ./app
```

含义粗略理解：

* `--check-stack-var=yes`：检查栈变量上的数据竞争，可能产生更多报告
* `--exclusive-threshold`：锁被某线程独占持有太久时报告
* `--shared-threshold`：读写锁共享持有太久时报告

初学时先不用加太多参数，先跑：

```bash
valgrind --tool=drd ./app
```

### 8.11 Helgrind / DRD 的误报和限制

多线程检测工具不是绝对真理。

常见误报来源：

* 使用了工具不认识的自定义同步原语
* lock-free 数据结构
* 原子操作和内存序比较复杂
* 第三方库内部同步方式特殊
* 线程池、协程运行时、系统库内部实现

排查时不要只看最后一行错误，要看：

* 哪块内存被多个线程访问
* 哪些线程在读写
* 是否真的缺少同步
* 是否所有访问都使用同一把锁
* 是否有 happens-before 关系

如果确认是第三方库内部误报，可以使用 suppression 文件过滤。

### 8.12 Suppression 文件

有些报告来自标准库、第三方库或已确认的无害路径。  
可以用 suppression 文件减少噪音。

先生成候选规则：

```bash
valgrind \
  --leak-check=full \
  --gen-suppressions=all \
  ./app
```

把确认要忽略的规则保存到：

```text
valgrind.supp
```

运行时使用：

```bash
valgrind \
  --leak-check=full \
  --suppressions=valgrind.supp \
  ./app
```

注意：

* suppression 只应该用于降低噪音
* 不要把自己业务代码里的真实泄漏压掉
* 每条 suppression 最好写注释说明为什么忽略

### 8.13 和 Sanitizer 怎么配合

Sanitizer 和 Valgrind 不是谁替代谁。

更实用的分工：

| 工具 | 优点 | 缺点 | 适合 |
| --- | --- | --- | --- |
| ASan / LSan | 快，适合开发和 CI | 需要重新编译，某些环境受限 | 新代码、单元测试 |
| TSan | 查数据竞争强 | 慢，内存开销大，需要编译插桩 | 多线程数据竞争 |
| Valgrind Memcheck | 不需要插桩，历史二进制也能查一部分 | 很慢，对平台支持有限 | 存量代码、泄漏排查 |
| Helgrind / DRD | 不需要 TSan 编译，能查线程问题 | 慢，可能误报 | 多线程疑难问题辅助排查 |

一个常见工程策略：

```text
开发阶段：ASan / LSan / TSan
存量排查：Valgrind Memcheck
多线程疑难问题：TSan + Helgrind / DRD 交叉验证
```

### 8.14 实战排查流程

推荐流程：

1. 先写一个能稳定复现问题的最小场景
2. 用 Debug 构建编译，保留 `-g`
3. 先跑 `memcheck`，修掉明确内存错误
4. 再看 `definitely lost` 和 `indirectly lost`
5. 如果是多线程问题，再跑 `helgrind` 或 `drd`
6. 对每条报告定位到自己的代码调用栈
7. 修复后重新跑同一个场景确认报告消失
8. 最后把关键场景固化成测试

命令模板：

```bash
# 1. 内存泄漏和内存错误
valgrind --tool=memcheck \
  --leak-check=full \
  --show-leak-kinds=all \
  --track-origins=yes \
  --error-exitcode=1 \
  ./app

# 2. 多线程 data race
valgrind --tool=helgrind ./app

# 3. 另一种线程检查
valgrind --tool=drd ./app
```

### 8.15 Valgrind 报告怎么看

看报告时按这个顺序：

1. **错误类型**
   例如 `Invalid write`、`Invalid read`、`definitely lost`、`Possible data race`。

2. **访问大小**
   例如 `size 4` 通常对应 `int`，`size 8` 可能对应指针或 `long long`。

3. **错误地址属于哪里**
   Valgrind 经常会提示这块地址是在已释放内存里、堆块边界外，还是栈上。

4. **分配栈**
   这块内存在哪里 `new` / `malloc` 出来的。

5. **释放栈**
   如果是 use-after-free，要看它在哪里已经被释放。

6. **当前访问栈**
   这次非法读写发生在哪里。

实际修 bug 时，最关键的是：

```text
分配位置 + 释放位置 + 出错访问位置
```

把这三条路径串起来，通常就能看出生命周期哪里错了。

---

## 9. 工程里的泄漏管理清单

真正有效的治理，通常不是靠某一个工具，而是靠几条长期规则：

* 新代码默认不写“拥有语义的裸指针”
* 业务代码里尽量不直接出现 `new` / `delete`
* 工厂接口优先返回 `std::unique_ptr`
* 容器里优先放对象或智能指针，不放“需要人工回收”的裸指针
* 第三方资源在进入系统边界时立即封装成 RAII 类型
* `shared_ptr` 关系图需要专门检查循环引用
* 测试或 CI 中固定开启 Sanitizer 版本
* 对缓存、对象池、队列设置上限，而不是默认无限增长

这才叫“管理”，不是出了问题再临时抓日志。

---

## 10. 一页总结

最值得记住的五条：

1. 泄漏治理的核心不是“记得释放”，而是明确所有权
2. 默认优先值语义、栈对象和 RAII
3. 动态分配优先 `unique_ptr`，不是裸指针
4. `shared_ptr` 最大的风险是循环引用
5. 用 Sanitizer 和 Valgrind 查问题，不要靠肉眼猜

参考：https://zhuanlan.zhihu.com/p/15101814919
如果只记一句：

> 预防内存泄漏最有效的方法，不是手写更多 `delete`，而是让代码结构默认不需要手写 `delete`。

---

# [15]STL容器、迭代器与算法实践

# STL 容器、迭代器与算法实践

时间：2026/05/04

> 关键词：容器选择、迭代器失效、标准算法、比较器、查找、排序、erase-remove、复杂度  
> 核心目标：建立工程里选择容器和使用标准算法的基本判断，不把 STL 只当成“会 push_back 的工具箱”。

---

## 1. 为什么还要单独学 STL 容器和算法

现代 C++ 里，很多代码质量问题不是语法问题，而是：

* 容器选错
* 复杂度误判
* 迭代器失效
* 手写循环替代标准算法
* 比较器写错导致排序或查找出问题

标准库容器和算法的价值不只是“少写代码”，而是：

* 让意图更明确
* 让复杂度更可预期
* 让边界条件更少出错

---

## 2. 容器选择先看访问模式

常见容器可以先这样粗略分类：

| 容器 | 适合场景 | 典型代价 |
| --- | --- | --- |
| `std::vector` | 连续存储、随机访问、尾部追加 | 中间插删慢，扩容会搬迁 |
| `std::deque` | 两端插删、随机访问 | 不保证整体连续 |
| `std::list` | 已有迭代器位置的频繁插删 | 缓存不友好，随机访问慢 |
| `std::map` | 有序键值、稳定迭代顺序 | 红黑树，查找 `O(log n)` |
| `std::unordered_map` | 哈希查找、平均快速访问 | 无序，rehash 会失效 |
| `std::set` | 有序唯一集合 | 插入查找 `O(log n)` |
| `std::unordered_set` | 哈希唯一集合 | 依赖 hash 质量 |

经验上：

* 默认先考虑 `std::vector`
* 需要按 key 查找时考虑 `unordered_map` / `map`
* 不要因为“中间插删”就马上用 `list`

很多时候 `vector` 即使中间移动元素，也可能因为缓存友好而比链表快。

---

## 3. `vector` 为什么经常是默认答案

`vector` 的优势来自连续内存：

* 遍历快
* 随机访问快
* 缓存友好
* 容易和 C API 交互

```cpp
#include <vector>

std::vector<int> xs;
xs.reserve(1000);

for (int i = 0; i < 1000; ++i) {
    xs.push_back(i);
}
```

如果你大概知道元素数量，`reserve` 通常是最简单有效的优化。

需要注意：

* `reserve` 改 capacity，不改 size
* `resize` 改 size，会真的构造元素
* 扩容会让原来的指针、引用、迭代器失效

---

## 4. 迭代器失效规则要主动记

迭代器失效是 STL 里非常常见的 bug 来源。

### 4.1 `vector`

发生扩容时：

* 所有迭代器失效
* 所有指针和引用也失效

中间 `insert/erase` 时：

* 插入点或删除点之后的迭代器通常失效

### 4.2 `deque`

`deque` 的失效规则比 `vector` 更复杂。  
如果代码依赖长期保存迭代器，要查清具体操作的规则。

### 4.3 `map` / `set`

节点式有序容器一般比较稳定：

* 插入通常不影响已有迭代器
* 删除某个元素只让指向该元素的迭代器失效

### 4.4 `unordered_map` / `unordered_set`

rehash 时：

* 迭代器会失效

但指向元素的引用和指针通常仍然有效，前提是元素没有被删除。

---

## 5. 删除元素：erase-remove 惯用法

从 `vector` 删除满足条件的元素，经典写法是：

```cpp
#include <algorithm>
#include <vector>

void remove_even(std::vector<int>& xs) {
    xs.erase(
        std::remove_if(xs.begin(), xs.end(), [](int x) {
            return x % 2 == 0;
        }),
        xs.end()
    );
}
```

`std::remove_if` 不会真的缩短容器，它只是把要保留的元素前移，并返回新的逻辑尾部。  
真正删除尾部多余元素的是 `erase`。

C++20 起可以直接用：

```cpp
#include <vector>

std::erase_if(xs, [](int x) {
    return x % 2 == 0;
});
```

更短，也更不容易写错。

---

## 6. 优先使用标准算法表达意图

与其写：

```cpp
bool found = false;
for (int x : xs) {
    if (x == target) {
        found = true;
        break;
    }
}
```

不如写：

```cpp
#include <algorithm>

bool found = std::find(xs.begin(), xs.end(), target) != xs.end();
```

常用算法：

| 算法 | 用途 |
| --- | --- |
| `std::find` | 查找等于某值的元素 |
| `std::find_if` | 查找满足条件的元素 |
| `std::any_of` | 是否至少一个满足 |
| `std::all_of` | 是否全部满足 |
| `std::none_of` | 是否全部不满足 |
| `std::count_if` | 统计满足条件的数量 |
| `std::sort` | 排序 |
| `std::stable_sort` | 稳定排序 |
| `std::lower_bound` | 有序区间二分下界 |
| `std::partition` | 按条件分区 |

算法名字本身就是文档。

---

## 7. 排序和比较器

`std::sort` 要求比较器满足严格弱序。

正确写法：

```cpp
#include <algorithm>
#include <string>
#include <vector>

struct User {
    int id;
    std::string name;
};

void sort_users(std::vector<User>& users) {
    std::sort(users.begin(), users.end(), [](const User& a, const User& b) {
        return a.id < b.id;
    });
}
```

危险写法：

```cpp
return a.id <= b.id; // 错
```

比较器不是“是否排在前面或相等”，而是：

> `a` 是否严格排在 `b` 前面。

如果比较器违反规则，排序结果可能不稳定，甚至触发未定义行为。

---

## 8. 二分查找的前提

`std::lower_bound` 和 `std::binary_search` 的前提是：

* 区间已经按同一规则有序

```cpp
#include <algorithm>
#include <vector>

bool contains_sorted(const std::vector<int>& xs, int value) {
    return std::binary_search(xs.begin(), xs.end(), value);
}
```

如果区间没有排序，二分查找没有意义。

常见模式：

```cpp
auto it = std::lower_bound(xs.begin(), xs.end(), value);
if (it != xs.end() && *it == value) {
    // found
}
```

---

## 9. `map` 和 `unordered_map` 怎么选

优先问几个问题：

1. 是否需要按 key 有序遍历？
2. 是否需要范围查询？
3. key 有没有稳定可靠的 hash？
4. 是否关心最坏情况复杂度？

大致规则：

* 需要顺序或范围查询：`std::map`
* 只需要 key 到 value 的快速查询：`std::unordered_map`
* 数据量很小：有时 `vector<pair<K,V>>` 线性查找也够用

小数据上不要盲目迷信哈希表。  
哈希计算、桶、节点分配都不是免费的。

---

## 10. 不要滥用 `operator[]`

`map` / `unordered_map` 的 `operator[]` 如果 key 不存在，会插入默认值。

```cpp
std::unordered_map<std::string, int> count;
int n = count["missing"]; // 插入 {"missing", 0}
```

如果只是查询，优先用：

```cpp
auto it = count.find("missing");
if (it != count.end()) {
    // use it->second
}
```

C++20 可以用：

```cpp
if (count.contains("missing")) {
    // found
}
```

---

## 11. `emplace` 不是永远比 `push_back` 好

`emplace_back` 的价值是原位构造：

```cpp
std::vector<std::string> names;
names.emplace_back(10, 'x');
```

但如果你已经有一个对象：

```cpp
std::string s = "hello";
names.push_back(s);
names.push_back(std::move(s));
```

这时 `push_back` 更清楚。  
不要把 `emplace` 当成“性能更强的 push”。

---

## 12. 常见坑

### 12.1 遍历时删除元素写错

删除元素后，原迭代器可能失效。  
需要使用 `erase` 返回的新迭代器，或者使用 `erase_if`。

### 12.2 对无序容器的遍历顺序有期待

`unordered_map` 不保证顺序。  
不同平台、不同运行时、rehash 后顺序都可能变化。

### 12.3 保存 `vector` 元素地址后继续 push

后续扩容可能让地址悬空。

### 12.4 比较器写成 `<=`

排序比较器必须表达严格小于关系。

### 12.5 在小数据量上过度复杂化

几十个元素的查找，用简单 `vector` 可能已经非常好。

---

## 13. 一页总结

STL 容器和算法最值得记住的是：

1. 默认优先考虑 `vector`，除非访问模式明确不适合
2. 先看复杂度，再看数据布局和缓存
3. 迭代器、引用、指针失效规则必须主动记
4. 标准算法能更准确表达意图
5. 排序比较器必须满足严格弱序
6. `map` / `unordered_map` 的选择取决于是否需要有序和范围查询

如果只记一句：

> 容器选择不是背 API，而是把访问模式、生命周期和复杂度放在一起判断。

---

## 14. 参考资料

1. cppreference: containers  
   <https://en.cppreference.com/w/cpp/container>

2. cppreference: algorithms  
   <https://en.cppreference.com/w/cpp/algorithm>

3. cppreference: iterator invalidation  
   <https://en.cppreference.com/w/cpp/container#Iterator_invalidation>

---

# [16]编译模型、链接与CMake入门

# 编译模型、链接与 CMake 入门

时间：2026/05/04

> 关键词：头文件、源文件、声明、定义、链接、ODR、静态库、动态库、CMake、target  
> 核心目标：理解 C++ 工程从源码到可执行文件的大致流程，避免头文件乱放、重复定义和 CMake 全局变量式写法。

---

## 1. 为什么现代 C++ 也必须懂编译模型

很多 C++ 工程问题表面上是“编译报错”，本质上是：

* 声明和定义混乱
* 头文件包含关系失控
* 重复定义违反 ODR
* 链接阶段找不到符号
* CMake 里 include path 和 link library 没有按 target 管理

懂编译模型的价值是：

* 知道错误发生在预处理、编译还是链接
* 知道哪些内容该放头文件，哪些该放 `.cpp`
* 知道库和可执行文件怎么组织

---

## 2. 从源码到程序的几个阶段

一个 C++ 文件大致经历：

1. 预处理：展开 `#include`、宏、条件编译
2. 编译：把翻译单元编译成目标文件
3. 汇编：生成机器码形式的 `.o` / `.obj`
4. 链接：把多个目标文件和库合成可执行文件或库

可以粗略理解成：

```text
main.cpp + include 的头文件
    -> 一个翻译单元
    -> main.o

foo.cpp + include 的头文件
    -> 一个翻译单元
    -> foo.o

main.o + foo.o + libraries
    -> app
```

头文件本身通常不会单独编译。  
它是被各个 `.cpp` 包含后，成为不同翻译单元的一部分。

---

## 3. 声明和定义

声明告诉编译器：

> 有这个名字，它的类型长这样。

```cpp
int add(int a, int b); // 函数声明
```

定义真正提供实体：

```cpp
int add(int a, int b) {
    return a + b;
}
```

变量也一样：

```cpp
extern int global_count; // 声明
int global_count = 0;    // 定义
```

常见组织方式：

```text
include/math.hpp   -> 声明
src/math.cpp       -> 定义
src/main.cpp       -> 使用
```

---

## 4. 头文件里应该放什么

通常适合放头文件：

* 类声明
* 函数声明
* 模板定义
* `inline` 函数定义
* `constexpr` 小函数
* 常量声明或 `inline constexpr` 变量

通常不适合放头文件：

* 普通全局变量定义
* 非 `inline` 普通函数定义
* 大量不必要的实现细节
* 会导致编译依赖爆炸的重型 include

错误例子：

```cpp
// bad.hpp
int counter = 0; // 被多个 cpp include 后会重复定义
```

更合适：

```cpp
// counter.hpp
extern int counter;

// counter.cpp
int counter = 0;
```

C++17 起，如果确实想在头文件定义全局常量，可以用：

```cpp
inline constexpr int max_retry = 3;
```

---

## 5. ODR：一个定义规则

ODR 是：

> One Definition Rule

粗略说：

* 一个具有外部链接的实体，在整个程序里通常只能有一个定义
* 类、模板、`inline` 函数可以出现在多个翻译单元，但定义必须一致

典型 ODR 问题：

```cpp
// util.hpp
int twice(int x) {
    return x * 2;
}
```

如果这个头文件被多个 `.cpp` 包含，就可能链接时报重复定义。

修正：

```cpp
// util.hpp
inline int twice(int x) {
    return x * 2;
}
```

或者：

```cpp
// util.hpp
int twice(int x);

// util.cpp
int twice(int x) {
    return x * 2;
}
```

---

## 6. 为什么模板通常写在头文件

模板不是普通函数。  
编译器需要在使用点看到模板定义，才能根据具体类型实例化代码。

```cpp
template <class T>
T max_value(T a, T b) {
    return a < b ? b : a;
}
```

如果只把模板声明放头文件、定义放 `.cpp`，其他翻译单元通常没法实例化它。

所以模板库常见形态是：

* 大量实现放在头文件
* 或者放在 `.ipp` / `.inl` 后再被头文件 include

---

## 7. 链接错误怎么读

常见链接错误：

### 7.1 undefined reference / undefined symbol

意思是：

* 编译器看到了声明
* 链接器找不到定义

常见原因：

* `.cpp` 没加入构建
* 忘记链接某个库
* 函数签名声明和定义不一致
* 模板定义不可见

### 7.2 duplicate symbol / multiple definition

意思是：

* 同一个外部符号有多个定义

常见原因：

* 普通函数定义写进头文件但没加 `inline`
* 全局变量定义写进头文件
* 同一个 `.cpp` 被错误地编进多个目标

---

## 8. 静态库和动态库

静态库：

* Linux/macOS 常见 `.a`
* Windows 常见 `.lib`
* 链接时把需要的目标代码合进最终产物

动态库：

* Linux `.so`
* macOS `.dylib`
* Windows `.dll`
* 程序运行时加载库代码

工程实践里要关心：

* 头文件提供编译期声明
* 库文件提供链接期或运行期实现
* ABI 边界要谨慎暴露 STL 类型、异常、内存分配策略

---

## 9. CMake 的核心是 target

现代 CMake 不建议把所有配置堆进全局变量。  
更推荐围绕 target 写：

```cmake
cmake_minimum_required(VERSION 3.20)
project(demo LANGUAGES CXX)

add_library(core
    src/math.cpp
)

target_include_directories(core
    PUBLIC
        include
)

target_compile_features(core
    PUBLIC
        cxx_std_20
)

add_executable(app
    src/main.cpp
)

target_link_libraries(app
    PRIVATE
        core
)
```

这里的依赖关系是：

```text
app -> core
```

`core` 的 public include path 会传递给链接它的 target。

---

## 10. `PUBLIC` / `PRIVATE` / `INTERFACE`

这三个词是现代 CMake 的核心。

| 关键字 | 当前 target 使用 | 依赖当前 target 的别人使用 |
| --- | --- | --- |
| `PRIVATE` | 是 | 否 |
| `PUBLIC` | 是 | 是 |
| `INTERFACE` | 否 | 是 |

例子：

```cmake
target_include_directories(core
    PUBLIC include
    PRIVATE src
)
```

含义：

* `core` 自己能 include `include` 和 `src`
* 依赖 `core` 的 target 只能继承 `include`

经验规则：

* 头文件里需要暴露给使用者的 include path：`PUBLIC`
* 只有 `.cpp` 内部使用的 include path：`PRIVATE`
* header-only 库：常用 `INTERFACE`

---

## 11. 一个常见工程结构

```text
project/
    CMakeLists.txt
    include/
        demo/
            math.hpp
    src/
        math.cpp
        main.cpp
    tests/
        math_test.cpp
```

头文件：

```cpp
// include/demo/math.hpp
#pragma once

namespace demo {

int add(int a, int b);

}
```

实现：

```cpp
// src/math.cpp
#include "demo/math.hpp"

namespace demo {

int add(int a, int b) {
    return a + b;
}

}
```

使用：

```cpp
// src/main.cpp
#include "demo/math.hpp"

int main() {
    return demo::add(1, 2);
}
```

---

## 12. include guard 和 `#pragma once`

传统 include guard：

```cpp
#ifndef DEMO_MATH_HPP
#define DEMO_MATH_HPP

int add(int a, int b);

#endif
```

现代工程里也常用：

```cpp
#pragma once
```

两者目的都是避免同一个头文件在一个翻译单元内被重复包含。  
注意它们解决的是“重复包含”，不是跨多个 `.cpp` 的重复定义。

---

## 13. 降低编译依赖

C++ 大项目编译慢，常常是 include 依赖太重。

常见做法：

* 头文件少 include，能前向声明就前向声明
* 实现细节放 `.cpp`
* 大型第三方头只在 `.cpp` 包含
* 公共头文件保持稳定

例子：

```cpp
// widget.hpp
#pragma once

#include <memory>

class Impl;

class Widget {
public:
    Widget();
    ~Widget();

private:
    std::unique_ptr<Impl> impl_;
};
```

这就是常说的 Pimpl 思路。  
它能减少头文件暴露的实现细节，但会引入一次间接访问和动态分配成本。

---

## 14. 常见坑

### 14.1 把普通函数定义放头文件

如果没有 `inline`，多个翻译单元包含后可能重复定义。

### 14.2 `.cpp` 没加入 CMake target

这通常会导致 undefined symbol。

### 14.3 include path 靠全局变量到处扩散

现代 CMake 更推荐 target 管理依赖。

### 14.4 头文件包含太重

会让一点小改动触发大量重编译。

### 14.5 混淆编译错误和链接错误

编译错误通常发生在单个翻译单元。  
链接错误通常发生在多个目标文件合并时。

---

## 15. 一页总结

这篇最值得记住的是：

1. `.cpp` 加上它 include 的头文件形成翻译单元
2. 声明让编译通过，定义让链接通过
3. 普通函数和全局变量定义不要随便放头文件
4. 模板通常需要在使用点可见，所以常放头文件
5. 现代 CMake 应围绕 target 管理 include、features 和 link
6. `PUBLIC` / `PRIVATE` / `INTERFACE` 表达依赖是否传递

如果只记一句：

> C++ 工程不是把文件堆在一起编译，而是把翻译单元、符号和 target 依赖组织清楚。

---

## 16. 参考资料

1. cppreference: translation phases  
   <https://en.cppreference.com/w/cpp/language/translation_phases>

2. cppreference: definitions and ODR  
   <https://en.cppreference.com/w/cpp/language/definition>

3. CMake: target_include_directories  
   <https://cmake.org/cmake/help/latest/command/target_include_directories.html>

4. CMake: target_link_libraries  
   <https://cmake.org/cmake/help/latest/command/target_link_libraries.html>

---

# [17]测试、调试与Sanitizer工具链

# 测试、调试与 Sanitizer 工具链

时间：2026/05/04

> 关键词：单元测试、集成测试、断言、日志、调试器、AddressSanitizer、UBSan、TSan、CI  
> 核心目标：把“代码看起来对”变成“有测试、有诊断、有工具能抓问题”的工程流程。

---

## 1. 为什么 C++ 更需要工具链意识

C++ 的自由度很高，也意味着很多错误不会自动变成清晰异常：

* 越界访问
* use-after-free
* 数据竞争
* 未定义行为
* 资源泄漏
* ODR 或链接问题

所以现代 C++ 实践里，测试和诊断工具不是附属品，而是基本能力。

一个比较健康的本地开发流程是：

1. 写小而明确的单元测试
2. Debug 模式开启断言和诊断
3. 定期跑 Sanitizer 版本
4. CI 固定跑核心测试集

---

## 2. 测试分层

常见测试可以粗略分三层：

| 类型 | 目标 | 特点 |
| --- | --- | --- |
| 单元测试 | 验证一个函数或类 | 快、边界清楚 |
| 集成测试 | 验证多个模块协作 | 更接近真实路径 |
| 回归测试 | 固定历史 bug | 防止问题再次出现 |

不要一上来只写“大而全”的测试。  
越底层的逻辑，越适合用小测试钉住行为。

---

## 3. 一个最小测试例子

即使不用测试框架，也可以先写最小可运行测试：

```cpp
#include <cassert>

int add(int a, int b) {
    return a + b;
}

int main() {
    assert(add(1, 2) == 3);
    assert(add(-1, 1) == 0);
}
```

这种测试很朴素，但比“手动运行看一眼输出”可靠。

工程里常用测试框架：

* GoogleTest
* Catch2
* doctest

框架的价值是：

* 更好的失败信息
* 测试组织
* fixture
* 参数化测试
* 和 CI 集成更自然

---

## 4. 测试什么

优先测试这些东西：

* 边界条件
* 空输入
* 错误路径
* 所有权转移
* 异常或错误返回
* 并发关闭流程
* 之前出过 bug 的路径

例子：

```cpp
#include <optional>
#include <string_view>

std::optional<int> parse_digit(std::string_view s) {
    if (s.size() != 1) return std::nullopt;
    if (s[0] < '0' || s[0] > '9') return std::nullopt;
    return s[0] - '0';
}
```

至少应该覆盖：

* `"0"`
* `"9"`
* `""`
* `"12"`
* `"x"`

---

## 5. 断言的作用

断言适合检查：

* 前置条件
* 内部不变量
* 理论上不该发生的状态

```cpp
#include <cassert>
#include <vector>

int get_first(const std::vector<int>& xs) {
    assert(!xs.empty());
    return xs.front();
}
```

断言不是错误处理。  
如果空输入是正常业务失败，应该返回错误或抛异常，而不是只写 `assert`。

注意：

* 定义 `NDEBUG` 后，标准 `assert` 会被移除
* 不要把有副作用的表达式写进 `assert`

---

## 6. 日志和调试器各自解决什么

日志适合：

* 线上或长时间运行问题
* 记录关键状态转移
* 还原错误发生前后的上下文

调试器适合：

* 本地复现
* 观察变量
* 单步执行
* 查看调用栈

不要把日志当成测试，也不要用调试器代替可重复测试。  
测试负责固定行为，日志和调试器负责定位问题。

---

## 7. AddressSanitizer：先抓内存错误

AddressSanitizer 常用于发现：

* 越界访问
* use-after-free
* double-free
* 部分内存泄漏问题

常见编译方式：

```bash
clang++ -std=c++20 -g -O1 -fno-omit-frame-pointer -fsanitize=address main.cpp -o app
./app
```

建议加上：

```bash
-fno-omit-frame-pointer
```

这样栈回溯通常更清楚。

如果需要 leak 检测：

```bash
ASAN_OPTIONS=detect_leaks=1 ./app
```

---

## 8. UndefinedBehaviorSanitizer

UBSan 常用于发现未定义行为，例如：

* 有符号整数溢出
* 非法类型转换
* 错误对齐访问
* 除零
* 某些无效 enum 值

常见编译方式：

```bash
clang++ -std=c++20 -g -O1 -fsanitize=undefined main.cpp -o app
./app
```

也可以和 ASan 一起用：

```bash
clang++ -std=c++20 -g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined main.cpp -o app
```

很多 UB 在普通运行时看不出问题，但会让优化器基于错误假设重写代码。  
所以 UBSan 对 C++ 很有价值。

---

## 9. ThreadSanitizer

TSan 用于发现数据竞争：

```bash
clang++ -std=c++20 -g -O1 -fsanitize=thread main.cpp -o app
./app
```

适合检查：

* 非原子共享变量并发读写
* 锁保护不一致
* 错误的对象发布

注意：

* TSan 运行开销较大
* 不建议和 ASan 在同一个构建里混用
* 对某些平台和第三方库支持有限

并发 bug 很难靠肉眼检查完整，TSan 是非常重要的辅助工具。

---

## 10. Debug / Release / RelWithDebInfo

常见构建类型：

| 类型 | 特点 |
| --- | --- |
| Debug | 无优化或低优化，调试友好 |
| Release | 高优化，性能接近发布 |
| RelWithDebInfo | 带调试信息的优化构建 |

排查性能或线上问题时，`RelWithDebInfo` 很有用：

* 接近真实优化路径
* 保留栈信息和符号

不要只在 Debug 下测试。  
有些 UB、时序问题、未初始化问题会在 Release 下更容易暴露。

---

## 11. CMake 里加测试

一个最小结构：

```cmake
enable_testing()

add_executable(math_test
    tests/math_test.cpp
)

target_link_libraries(math_test
    PRIVATE
        core
)

add_test(NAME math_test COMMAND math_test)
```

运行：

```bash
ctest --test-dir build --output-on-failure
```

如果使用 GoogleTest，通常还会用它提供的测试发现工具。  
但底层原则不变：

* 测试本身也是一个 target
* 测试链接被测库
* `ctest` 统一运行测试

---

## 12. CMake 里加 Sanitizer 选项

小项目可以先写得简单：

```cmake
option(ENABLE_ASAN "Enable AddressSanitizer" OFF)

if(ENABLE_ASAN)
    add_compile_options(-fsanitize=address -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address)
endif()
```

更工程化的写法是把 Sanitizer 配置绑定到具体 target，避免污染第三方库。

例如：

```cmake
target_compile_options(app PRIVATE -fsanitize=address -fno-omit-frame-pointer)
target_link_options(app PRIVATE -fsanitize=address)
```

不要只加编译选项，链接阶段也要加对应 sanitizer。

---

## 13. 最小 CI 检查清单

一个实用的 C++ CI 至少可以包含：

1. 普通 Debug 构建
2. 普通 Release 或 RelWithDebInfo 构建
3. 单元测试
4. ASan + UBSan 测试
5. 关键并发模块定期跑 TSan

如果项目更成熟，还可以加：

* clang-tidy
* clang-format 检查
* 覆盖率
* benchmark 回归
* 包管理和依赖版本锁定

先把最关键的测试和 sanitizer 跑起来，比一开始追求全套流程更重要。

---

## 14. 常见坑

### 14.1 只测正常路径

错误路径和边界条件更容易藏 bug。

### 14.2 把 `assert` 当成用户输入校验

Release 下断言可能被移除。  
可恢复错误应该走错误处理流程。

### 14.3 只在 Debug 下运行

Release 优化可能暴露完全不同的问题。

### 14.4 Sanitizer 只加了编译选项

链接阶段也需要对应选项。

### 14.5 把 TSan 报告轻易忽略

数据竞争不是“小概率问题”，而是未定义行为。

---

## 15. 一页总结

测试和工具链最值得记住的是：

1. 单元测试负责固定小范围行为
2. 回归测试负责防止历史 bug 回来
3. 断言检查内部不变量，不替代错误处理
4. ASan 抓内存错误，UBSan 抓未定义行为，TSan 抓数据竞争
5. Debug 和 Release 都要测
6. CMake 里测试和 sanitizer 最好按 target 管理

如果只记一句：

> 现代 C++ 工程要靠测试、断言、日志、调试器和 Sanitizer 共同兜底，不能只靠“我看代码应该没问题”。

---

## 16. 参考资料

1. Clang AddressSanitizer  
   <https://clang.llvm.org/docs/AddressSanitizer.html>

2. Clang UndefinedBehaviorSanitizer  
   <https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html>

3. Clang ThreadSanitizer  
   <https://clang.llvm.org/docs/ThreadSanitizer.html>

4. CMake: testing  
   <https://cmake.org/cmake/help/latest/manual/ctest.1.html>

---

# [18]const正确性、API设计与现代属性

# const 正确性、API 设计与现代属性

时间：2026/05/08

> 关键词：`const`、引用、值传递、`explicit`、`[[nodiscard]]`、`noexcept`、`enum class`、API 边界  
> 核心目标：把“函数签名”写成清楚的契约，让调用者一眼知道所有权、可变性、失败方式和使用方式。

---

## 1. API 设计先看函数签名

函数签名不是只给编译器看的，它也是给人看的。

一个好的签名应该回答：

1. 参数会不会被修改
2. 参数会不会被保存
3. 返回值是否必须检查
4. 函数是否可能抛异常
5. 构造是否允许隐式转换
6. 调用者是否转移所有权

对比两个接口：

```cpp
void parse(char* data, int len);
```

和：

```cpp
[[nodiscard]] Config parse_config(std::string_view text);
```

第二个签名更清楚：

* 输入只是观察，不拥有
* 输入不会被修改
* 返回值值得检查
* 解析结果是一个明确对象

---

## 2. `const` 参数：表达“我不会改它”

读大对象时，优先用 `const T&`：

```cpp
struct User {
    std::string name;
    std::string email;
};

void print_user(const User& user) {
    std::cout << user.name << " <" << user.email << ">\n";
}
```

如果写成值传递：

```cpp
void print_user(User user);
```

会拷贝整个对象，通常没有必要。

如果参数很小，值传递更简单：

```cpp
void set_retry_count(int n);
void set_timeout(std::chrono::milliseconds timeout);
```

经验：

* 小标量：值传递
* 大对象只读：`const T&`
* 可空观察：`const T*`
* 连续数组观察：`std::span<const T>`
* 字符串观察：`std::string_view`

---

## 3. `const` 成员函数：承诺不改对象状态

成员函数后面的 `const` 表示不会修改这个对象的可观察状态：

```cpp
class Cache {
public:
    std::size_t size() const {
        return items_.size();
    }

    bool empty() const {
        return items_.empty();
    }

private:
    std::vector<int> items_;
};
```

如果一个查询函数没写 `const`：

```cpp
std::size_t size();
```

那么 `const Cache&` 就不能调用它。  
这会让 API 很难组合。

---

## 4. 什么时候用 `mutable`

`mutable` 用于“逻辑上不改变对象，但需要更新内部缓存”的场景。

```cpp
class Text {
public:
    explicit Text(std::string s) : data_(std::move(s)) {}

    std::size_t word_count() const {
        if (!cached_) {
            cached_words_ = count_words(data_);
            cached_ = true;
        }
        return cached_words_;
    }

private:
    static std::size_t count_words(std::string_view text);

    std::string data_;
    mutable bool cached_ = false;
    mutable std::size_t cached_words_ = 0;
};
```

注意：

* `mutable` 不是绕过 const 的万能钥匙
* 多线程读同一个对象时，mutable 缓存也需要同步
* 如果缓存逻辑复杂，优先考虑显式构建缓存对象

---

## 5. 字符串参数优先考虑 `std::string_view`

只读、不保存字符串时：

```cpp
void log_message(std::string_view msg) {
    std::cout << msg << "\n";
}
```

它可以接收：

```cpp
log_message("hello");

std::string s = "world";
log_message(s);

std::string_view v = "cpp";
log_message(v);
```

但不要保存 `string_view` 指向临时对象：

```cpp
class Bad {
public:
    void set_name(std::string_view name) {
        name_ = name; // 危险：name 可能指向临时字符串
    }

private:
    std::string_view name_;
};
```

如果对象要保存字符串，应该拥有它：

```cpp
class User {
public:
    void set_name(std::string name) {
        name_ = std::move(name);
    }

private:
    std::string name_;
};
```

---

## 6. 连续数组参数优先考虑 `std::span`

传统接口：

```cpp
double average(const double* data, std::size_t n);
```

现代写法：

```cpp
#include <span>
#include <numeric>

double average(std::span<const double> xs) {
    if (xs.empty()) {
        return 0.0;
    }

    double sum = std::accumulate(xs.begin(), xs.end(), 0.0);
    return sum / static_cast<double>(xs.size());
}
```

可以接收：

```cpp
std::vector<double> v{1.0, 2.0, 3.0};
std::array<double, 3> a{1.0, 2.0, 3.0};
double raw[] = {1.0, 2.0, 3.0};

average(v);
average(a);
average(raw);
```

`span` 只观察，不拥有。  
不要让 `span` 活得比底层数组更久。

---

## 7. 值传递 + move：接收要保存的对象

如果函数要把参数保存到成员里，经常可以用值传递：

```cpp
class Person {
public:
    explicit Person(std::string name)
        : name_(std::move(name)) {}

    void rename(std::string name) {
        name_ = std::move(name);
    }

private:
    std::string name_;
};
```

调用者传左值时会拷贝一次：

```cpp
std::string n = "Alice";
Person p(n); // 拷贝进参数，再 move 到成员
```

调用者传右值时通常很高效：

```cpp
Person p("Alice");
Person q(std::string("Bob"));
```

这比同时写 `const std::string&` 和 `std::string&&` 两套重载更简单。

---

## 8. `explicit`：阻止意外隐式转换

单参数构造函数默认可能触发隐式转换：

```cpp
class Port {
public:
    Port(int value) : value_(value) {}

private:
    int value_;
};

void connect(Port port);

connect(80); // 可以隐式把 int 转成 Port
```

很多时候这不是你想要的。  
更推荐：

```cpp
class Port {
public:
    explicit Port(int value) : value_(value) {}

private:
    int value_;
};

connect(Port{80}); // 调用者明确表达意图
```

经验：

> 除非你明确希望它能隐式转换，否则单参数构造函数优先写 `explicit`。

---

## 9. `[[nodiscard]]`：返回值不能随手丢

错误处理或资源构造结果经常不能忽略：

```cpp
enum class Error {
    none,
    file_not_found,
    permission_denied,
};

[[nodiscard]] Error save_config(std::string_view path);
```

调用者如果丢掉返回值，编译器会提醒：

```cpp
save_config("app.toml"); // 可能警告
```

更清晰的写法：

```cpp
if (auto err = save_config("app.toml"); err != Error::none) {
    report(err);
}
```

也可以标记类型：

```cpp
struct [[nodiscard]] Result {
    bool ok;
    std::string message;
};

Result load_user(int id);
```

适合 `[[nodiscard]]` 的返回值：

* 错误码
* `std::optional`
* `std::expected`
* 资源句柄
* 需要调用者继续使用的 builder 结果

---

## 10. `noexcept`：承诺不抛异常

`noexcept` 不只是优化提示，也是契约。

```cpp
#include <cstddef>
#include <utility>

class Buffer {
public:
    Buffer(Buffer&& other) noexcept
        : data_(std::exchange(other.data_, nullptr)),
          size_(std::exchange(other.size_, 0)) {}

private:
    int* data_ = nullptr;
    std::size_t size_ = 0;
};
```

移动构造如果是 `noexcept`，容器扩容时更愿意移动元素而不是拷贝元素。

不要乱写：

```cpp
void f() noexcept {
    may_throw(); // 如果真的抛出，会 std::terminate
}
```

经验：

* 析构函数默认应不抛
* 移动构造/移动赋值能保证不抛时写 `noexcept`
* 低层工具函数如果不抛，可以写 `noexcept`
* 不能保证时不要硬写

---

## 11. `enum class`：避免枚举污染和隐式转换

老式 enum：

```cpp
enum Color {
    red,
    green,
};

int x = red; // 可以隐式转 int
```

更推荐：

```cpp
enum class Color {
    red,
    green,
};

void paint(Color c);

paint(Color::red);
```

如果要指定底层类型：

```cpp
enum class HttpStatus : int {
    ok = 200,
    not_found = 404,
};
```

`enum class` 的好处：

* 名称不污染外层作用域
* 不会随便隐式转整数
* API 可读性更强

---

## 12. 现代属性的几个实用场景

### 12.1 `[[maybe_unused]]`

用于故意未使用的变量或参数：

```cpp
void on_debug_event([[maybe_unused]] int code) {
#ifdef DEBUG
    std::cout << code << "\n";
#endif
}
```

### 12.2 `[[deprecated]]`

给旧接口留迁移提示：

```cpp
[[deprecated("use parse_config_v2 instead")]]
Config parse_config(std::string_view text);
```

### 12.3 `[[fallthrough]]`

明确 switch 穿透是有意的：

```cpp
switch (level) {
case 3:
    enable_verbose();
    [[fallthrough]];
case 2:
    enable_info();
    break;
default:
    break;
}
```

这些属性不是装饰，它们让代码意图对编译器和读者都更清楚。

---

## 13. 返回值设计：值、引用、指针怎么选

### 13.1 返回值

最常见、最安全：

```cpp
std::vector<int> make_ids();
```

现代 C++ 有移动语义和返回值优化，不要过早改成输出参数。

### 13.2 返回引用

表示返回对象内部已有内容：

```cpp
class User {
public:
    const std::string& name() const noexcept {
        return name_;
    }

private:
    std::string name_;
};
```

注意调用者不能让引用超过对象生命周期。

### 13.3 返回指针

适合表达“可能没有”且不转移所有权：

```cpp
const User* find_user(int id) const;
```

如果没有值，也可以用：

```cpp
std::optional<User> find_user(int id) const;
```

如果对象很大、不想复制，并且不拥有，就用指针或引用包装语义说清楚。

---

## 14. 一个完整的小 API 示例

```cpp
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

enum class Role {
    admin,
    guest,
};

struct User {
    int id = 0;
    std::string name;
    Role role = Role::guest;
};

class UserStore {
public:
    explicit UserStore(std::vector<User> users)
        : users_(std::move(users)) {}

    [[nodiscard]] const User* find(int id) const noexcept {
        for (const auto& user : users_) {
            if (user.id == id) {
                return &user;
            }
        }
        return nullptr;
    }

    [[nodiscard]] std::vector<User> find_by_name(std::string_view name) const {
        std::vector<User> out;
        for (const auto& user : users_) {
            if (user.name == name) {
                out.push_back(user);
            }
        }
        return out;
    }

    void append(User user) {
        users_.push_back(std::move(user));
    }

    void append_all(std::span<const User> users) {
        users_.insert(users_.end(), users.begin(), users.end());
    }

private:
    std::vector<User> users_;
};
```

这个例子里：

* 构造函数 `explicit`
* 只读查询是 `const`
* 可能没有结果时返回指针
* 必须关注的查询结果加 `[[nodiscard]]`
* 保存参数时用值传递 + move
* 批量只读输入用 `span<const User>`

---

## 15. 常见误区

### 15.1 所有参数都写 `const T&`

小整数、枚举、轻量句柄直接值传递更好。

### 15.2 到处返回 `const T&`

如果返回的是临时对象或局部变量引用，会立刻悬空。  
现代 C++ 返回值通常很便宜，别怕返回对象。

### 15.3 `string_view` 当成字符串成员保存

除非你非常清楚底层字符串生命周期，否则成员里保存 `std::string`。

### 15.4 所有函数都加 `noexcept`

`noexcept` 是承诺，不是祝福。  
承诺错了会直接终止程序。

### 15.5 不写 `explicit`

隐式转换引起的问题很隐蔽。  
构造函数默认倾向 `explicit` 是很好的工程习惯。

---

## 16. 一页总结

现代 C++ API 设计最常用的几条规则：

1. 只读大对象用 `const T&`
2. 字符串观察用 `std::string_view`
3. 连续数组观察用 `std::span`
4. 要保存的对象可以值传递再 move
5. 查询成员函数尽量写 `const`
6. 单参数构造函数优先 `explicit`
7. 重要返回值加 `[[nodiscard]]`
8. 能保证不抛时才写 `noexcept`

一句话：

> 好 API 的核心是把所有权、可变性和失败语义写在签名里，而不是藏在文档里。

---

# [19]constexpr、consteval与编译期计算实践

# constexpr、consteval 与编译期计算实践

时间：2026/05/08

> 关键词：`constexpr`、`consteval`、`constinit`、`static_assert`、`if constexpr`、编译期校验  
> 核心目标：掌握现代 C++ 里“能在编译期算清楚的，就不要拖到运行期”的实用写法。

---

## 1. 编译期计算解决什么问题

有些值在编译时就已经确定：

* 数组大小
* 协议字段长度
* 哈希表种子
* 配置上限
* 类型分支
* 查表数据
* 模板泛型里的策略选择

如果能在编译期完成，就能得到几个收益：

1. 运行期少做重复计算
2. 错误更早暴露
3. 常量能进入类型系统
4. 优化器更容易生成好代码

但也不要把所有东西都搬到编译期。  
编译期计算会增加编译时间，也会让错误信息变复杂。

---

## 2. `constexpr` 变量

`constexpr` 变量必须能在编译期初始化：

```cpp
constexpr int max_clients = 1024;
constexpr double pi = 3.141592653589793;

std::array<int, max_clients> counters{};
```

和 `const` 的区别：

```cpp
const int runtime_value = read_config(); // 运行期常量
constexpr int compile_value = 42;        // 编译期常量
```

`const` 只表示之后不能改。  
`constexpr` 还要求初始化结果能作为编译期常量使用。

---

## 3. `constexpr` 函数：既能编译期，也能运行期

```cpp
constexpr int square(int x) {
    return x * x;
}

static_assert(square(5) == 25);

int runtime(int x) {
    return square(x); // x 运行期才知道，也可以调用
}
```

`constexpr` 函数不是“只能编译期调用”。  
它的意思是：

> 如果参数在编译期已知，并且函数满足规则，就可以在编译期求值。

---

## 4. 编译期校验：`static_assert`

`static_assert` 适合把约束写在代码里：

```cpp
constexpr std::size_t packet_header_size = 8;

static_assert(packet_header_size % 4 == 0,
              "packet header must be 4-byte aligned");
```

模板里更常见：

```cpp
template <class T>
void serialize(const T& value) {
    static_assert(std::is_trivially_copyable_v<T>,
                  "serialize requires trivially copyable type");

    write_bytes(&value, sizeof(T));
}
```

错误会在编译期出现，而不是等到线上数据坏掉。

---

## 5. 一个实用例子：编译期单位换算

```cpp
#include <chrono>

constexpr std::chrono::milliseconds frame_time(int fps) {
    return std::chrono::milliseconds(1000 / fps);
}

static_assert(frame_time(60).count() == 16);

constexpr auto tick = frame_time(50);
```

这类小函数比魔法数字更清晰：

```cpp
constexpr auto network_timeout = std::chrono::seconds(5);
constexpr auto render_budget = std::chrono::milliseconds(16);
```

---

## 6. `constexpr` 容器和查表

C++20 之后，很多标准库类型的 `constexpr` 能力更强。  
实际工程里最常见的是用 `std::array` 做编译期表：

```cpp
#include <array>

constexpr std::array<int, 10> make_squares() {
    std::array<int, 10> out{};
    for (std::size_t i = 0; i < out.size(); ++i) {
        out[i] = static_cast<int>(i * i);
    }
    return out;
}

constexpr auto squares = make_squares();

static_assert(squares[4] == 16);
```

这种写法适合：

* 小型查表
* 编码映射
* 固定协议表
* 编译期测试数据

---

## 7. `consteval`：必须编译期执行

`consteval` 函数被称为立即函数。  
它必须在编译期求值。

```cpp
consteval int port_literal(int port) {
    if (port <= 0 || port > 65535) {
        throw "invalid port";
    }
    return port;
}

constexpr int http_port = port_literal(80);
```

如果这样写：

```cpp
int p = read_port();
int x = port_literal(p); // 错：p 不是编译期常量
```

会编译失败。

适合 `consteval` 的场景：

* 编译期字面量校验
* 生成强类型常量
* 只允许编译期构造的描述符
* 防止运行期误用

---

## 8. `consteval` 做字符串校验

例如要求日志分类名非空且不超过长度：

```cpp
#include <string_view>

consteval std::string_view category(std::string_view name) {
    if (name.empty()) {
        throw "empty category";
    }
    if (name.size() > 16) {
        throw "category too long";
    }
    return name;
}

constexpr auto net = category("network");
```

如果写成：

```cpp
constexpr auto bad = category("");
```

编译期就能报错。  
这种写法适合把约束提前到编译阶段。

---

## 9. `constinit`：保证静态对象静态初始化

`constinit` 用于静态存储期变量，保证它不会发生动态初始化。

```cpp
constinit int global_counter = 0;
```

它不是 `const`：

```cpp
constinit int value = 1;

void f() {
    ++value; // 可以修改
}
```

但初始化必须是编译期可完成的：

```cpp
int read_config();

constinit int x = read_config(); // 错：不能动态初始化
```

适合：

* 全局计数器
* 静态状态
* 需要避免静态初始化顺序问题的对象

注意：

* `constinit` 保证初始化时机
* `constexpr` 保证值是常量表达式并隐含 const
* 两者关注点不同

---

## 10. `if constexpr`：编译期分支

泛型代码中，经常根据类型选择实现。

```cpp
#include <type_traits>
#include <string>

template <class T>
std::string to_text(const T& value) {
    if constexpr (std::is_integral_v<T>) {
        return std::to_string(value);
    } else if constexpr (std::is_floating_point_v<T>) {
        return std::to_string(value);
    } else {
        return value.to_string();
    }
}
```

`if constexpr` 的未选分支不会实例化。  
所以当 `T` 是整数时，编译器不会要求整数有 `to_string()` 成员函数。

这比以前用复杂 SFINAE 更容易读。

---

## 11. 编译期 hash：实用但要谨慎

一个简单的 FNV-1a 字符串 hash：

```cpp
#include <cstdint>
#include <string_view>

constexpr std::uint32_t fnv1a(std::string_view s) {
    std::uint32_t hash = 2166136261u;
    for (char c : s) {
        hash ^= static_cast<unsigned char>(c);
        hash *= 16777619u;
    }
    return hash;
}

static_assert(fnv1a("GET") != fnv1a("POST"));

constexpr auto get_id = fnv1a("GET");
```

可以用于：

* 协议命令 id
* 资源名映射
* switch 前的分类

但不要把 hash 当成绝对无冲突。  
如果冲突会造成严重问题，必须保留字符串二次校验。

---

## 12. 编译期解析小配置

可以写一个非常小的编译期 parser：

```cpp
#include <string_view>

consteval int parse_digit(char c) {
    if (c < '0' || c > '9') {
        throw "not a digit";
    }
    return c - '0';
}

consteval int parse_two_digits(std::string_view s) {
    if (s.size() != 2) {
        throw "expected two digits";
    }
    return parse_digit(s[0]) * 10 + parse_digit(s[1]);
}

constexpr int major = parse_two_digits("23");
```

这种代码适合非常小、非常固定的格式。  
不要把复杂 JSON/YAML 解析器搬到编译期，除非真的有明确收益。

---

## 13. 编译期和运行期复用同一套逻辑

`constexpr` 函数的一个好处是可以复用：

```cpp
constexpr bool is_power_of_two(std::size_t n) {
    return n != 0 && (n & (n - 1)) == 0;
}

static_assert(is_power_of_two(64));

bool validate_buffer_size(std::size_t n) {
    return is_power_of_two(n);
}
```

同一段逻辑：

* 编译期检查常量
* 运行期检查用户输入

这比维护两套实现更稳。

---

## 14. 类型级配置：用常量表达式控制模板

```cpp
#include <array>
#include <cstddef>
#include <stdexcept>

template <std::size_t Capacity>
class FixedBuffer {
public:
    static_assert(Capacity > 0);
    static_assert(Capacity <= 4096);

    constexpr std::size_t capacity() const noexcept {
        return Capacity;
    }

    void push(char c) {
        if (size_ == Capacity) {
            throw std::runtime_error("buffer full");
        }
        data_[size_++] = c;
    }

private:
    std::array<char, Capacity> data_{};
    std::size_t size_ = 0;
};

FixedBuffer<256> buffer;
```

`Capacity` 是类型的一部分。  
`FixedBuffer<128>` 和 `FixedBuffer<256>` 是不同类型。

适合：

* 固定容量队列
* 小缓冲
* 协议字段
* 数值维度

不适合运行期才知道大小的情况。

---

## 15. 编译期计算的常见限制

现代 C++ 的 `constexpr` 已经很强，但仍要注意：

* 不能做不允许的运行期 I/O
* 不能依赖运行期输入
* 编译期异常只用于让求值失败，不是运行期异常机制
* 编译期计算过重会拖慢编译
* 错误信息可能比运行期更难读

判断标准：

> 如果某个值是稳定常量、约束明确、错误越早越好，就适合编译期。

---

## 16. 常见误区

### 16.1 `constexpr` 一定更快

不一定。  
如果参数是运行期值，函数仍然运行期执行。

### 16.2 所有配置都放进模板参数

模板参数会制造更多类型和更多编译实例。  
运行期配置就老实用运行期数据。

### 16.3 `constinit` 等于不可修改

不等于。  
`constinit` 管初始化时机，`const` 管可修改性。

### 16.4 编译期 hash 可以完全替代字符串

不能。  
hash 有冲突风险，重要路径要二次校验。

### 16.5 编译期越多越现代

不是。  
工程里还要考虑编译时间、可读性和调试成本。

---

## 17. 一页总结

编译期计算最常用的工具：

1. `constexpr`：能编译期算，也能运行期用
2. `consteval`：必须编译期算
3. `constinit`：保证静态变量静态初始化
4. `static_assert`：编译期校验约束
5. `if constexpr`：泛型代码里的编译期分支

一句话：

> 编译期计算的价值不是炫技，而是把稳定规则提前验证，把重复计算提前完成。

---

# [20]C++20 concepts与泛型接口约束

# C++20 concepts 与泛型接口约束

时间：2026/05/08

> 关键词：concept、requires、泛型约束、`std::integral`、`std::ranges`、重载选择、错误信息  
> 核心目标：用 concepts 把模板参数的要求写清楚，让泛型接口更像普通接口一样可读、可诊断。

---

## 1. concepts 解决什么问题

传统模板很强，但错误信息经常很难读。

```cpp
template <class T>
auto add(T a, T b) {
    return a + b;
}
```

如果传入不支持 `+` 的类型，错误可能出现在很深的模板实例化里。  
concepts 的目标是把约束提前写出来：

```cpp
#include <concepts>

template <class T>
requires std::integral<T>
T add(T a, T b) {
    return a + b;
}
```

现在接口明确表示：

> 这里只接受整数类型。

---

## 2. 标准库已有 concepts

`<concepts>` 里有很多常用概念：

```cpp
#include <concepts>

static_assert(std::integral<int>);
static_assert(std::floating_point<double>);
static_assert(std::same_as<int, int>);
static_assert(std::convertible_to<int, double>);
```

常见的有：

* `std::same_as<T, U>`
* `std::derived_from<T, U>`
* `std::convertible_to<T, U>`
* `std::integral<T>`
* `std::floating_point<T>`
* `std::regular<T>`
* `std::predicate<F, Args...>`
* `std::invocable<F, Args...>`

优先用标准库已有概念，别急着自己造。

---

## 3. 三种常见写法

### 3.1 requires 子句

```cpp
template <class T>
requires std::integral<T>
T twice(T x) {
    return x * 2;
}
```

### 3.2 约束模板参数

```cpp
template <std::integral T>
T twice(T x) {
    return x * 2;
}
```

### 3.3 约束 `auto`

```cpp
std::integral auto twice(std::integral auto x) {
    return x * 2;
}
```

工程里常见选择：

* 简单函数：约束模板参数或约束 `auto`
* 约束复杂：写 `requires`
* 公共库接口：倾向写得更明确

---

## 4. 自定义 concept：从最小需求开始

假设你只要求类型能调用 `.size()` 并返回可转成 `std::size_t` 的值：

```cpp
#include <concepts>
#include <cstddef>

template <class T>
concept Sized = requires(const T& x) {
    { x.size() } -> std::convertible_to<std::size_t>;
};

template <Sized T>
std::size_t length(const T& x) {
    return static_cast<std::size_t>(x.size());
}
```

可以调用：

```cpp
std::string s = "hello";
std::vector<int> v{1, 2, 3};

length(s);
length(v);
```

注意：concept 应该描述“你真正需要什么”，不要过度指定类型。

---

## 5. `requires` 表达式怎么读

```cpp
#include <concepts>
#include <cstddef>
#include <functional>

template <class T>
concept Hashable = requires(T x) {
    { std::hash<T>{}(x) } -> std::convertible_to<std::size_t>;
};
```

含义：

* 给定一个 `T x`
* 表达式 `std::hash<T>{}(x)` 必须合法
* 返回值必须能转成 `std::size_t`

更复杂一点：

```cpp
#include <concepts>
#include <ostream>

template <class T>
concept Printable = requires(std::ostream& os, const T& value) {
    { os << value } -> std::same_as<std::ostream&>;
};
```

这个 concept 表示对象能被输出到流。

---

## 6. 用 concept 改善错误信息

没有约束的版本：

```cpp
template <class T>
void dump(const T& value) {
    std::cout << value << "\n";
}
```

约束后的版本：

```cpp
#include <concepts>
#include <iostream>

template <class T>
concept StreamWritable = requires(std::ostream& os, const T& value) {
    { os << value } -> std::same_as<std::ostream&>;
};

template <StreamWritable T>
void dump(const T& value) {
    std::cout << value << "\n";
}
```

当类型不满足条件时，编译器更容易告诉你：

```text
T does not satisfy StreamWritable
```

这比在 `operator<<` 深处爆炸更友好。

---

## 7. concept 参与重载选择

```cpp
#include <concepts>
#include <iostream>

void print_value(std::integral auto x) {
    std::cout << "integer: " << x << "\n";
}

void print_value(std::floating_point auto x) {
    std::cout << "float: " << x << "\n";
}

void print_value(const std::string& s) {
    std::cout << "string: " << s << "\n";
}
```

调用：

```cpp
print_value(42);
print_value(3.14);
print_value(std::string("hello"));
```

这比写一堆 `enable_if` 更直观。

---

## 8. 约束函数对象：`std::invocable`

泛型算法经常接收回调。

```cpp
#include <concepts>
#include <functional>
#include <vector>

template <class F>
requires std::invocable<F, int>
void repeat(int n, F f) {
    for (int i = 0; i < n; ++i) {
        std::invoke(f, i);
    }
}
```

使用：

```cpp
repeat(3, [](int i) {
    std::cout << i << "\n";
});
```

如果还要求返回 `bool`：

```cpp
template <class F>
requires std::predicate<F, int>
int count_if_index(int n, F pred) {
    int count = 0;
    for (int i = 0; i < n; ++i) {
        if (std::invoke(pred, i)) {
            ++count;
        }
    }
    return count;
}
```

---

## 9. 约束 range：和 ranges 配合

`<ranges>` 里也有很多 concept：

```cpp
#include <ranges>
#include <vector>
#include <iostream>

template <std::ranges::input_range R>
void print_all(const R& r) {
    for (const auto& x : r) {
        std::cout << x << "\n";
    }
}
```

如果要求能随机访问：

```cpp
template <std::ranges::random_access_range R>
auto middle(const R& r) {
    return r[std::ranges::size(r) / 2];
}
```

如果还要求元素类型是整数：

```cpp
#include <concepts>
#include <ranges>

template <class R>
concept IntegralRange =
    std::ranges::input_range<R> &&
    std::integral<std::ranges::range_value_t<R>>;

template <IntegralRange R>
long long sum_integrals(const R& r) {
    long long sum = 0;
    for (auto x : r) {
        sum += x;
    }
    return sum;
}
```

---

## 10. 避免过度约束

坏例子：

```cpp
template <class T>
concept VectorInt = std::same_as<T, std::vector<int>>;

template <VectorInt T>
int sum(const T& xs);
```

这个接口只能接收 `std::vector<int>`。  
但你真正需要的可能只是“一段整数 range”。

更好的写法：

```cpp
template <IntegralRange R>
long long sum(const R& xs) {
    long long out = 0;
    for (auto x : xs) {
        out += x;
    }
    return out;
}
```

这样可以接收：

* `std::vector<int>`
* `std::array<int, N>`
* `std::span<int>`
* ranges view

约束应该贴近需求，而不是贴近你当前想到的实现类型。

---

## 11. concept 不是运行期检查

concept 在编译期检查类型能力：

```cpp
template <std::integral T>
T divide(T a, T b) {
    return a / b;
}
```

它保证 `T` 是整数，但不保证：

```cpp
divide(10, 0); // 运行期仍然可能错误
```

所以概念约束不能替代运行期校验。

---

## 12. 用 concept 表达策略对象接口

```cpp
#include <concepts>
#include <string_view>

struct Request {
    std::string_view path;
};

struct Response {
    int status = 200;
};

template <class H>
concept Handler = requires(H h, const Request& req) {
    { h.handle(req) } -> std::same_as<Response>;
};

template <Handler H>
Response dispatch(H& handler, const Request& req) {
    return handler.handle(req);
}
```

实现一个 handler：

```cpp
struct HealthHandler {
    Response handle(const Request& req) {
        if (req.path == "/health") {
            return Response{200};
        }
        return Response{404};
    }
};
```

这个接口没有强迫继承，也没有虚函数。  
只要类型满足结构要求，就能用。

这就是静态多态的一种实践。

---

## 13. concepts 和多态的选择

用 concepts：

* 编译期确定类型
* 性能敏感
* 希望内联
* 模板库
* 策略对象

用虚函数：

* 运行期动态选择类型
* ABI 边界更稳定
* 插件式加载
* 需要统一容器保存不同派生对象

两者不是谁取代谁。  
它们分别服务于静态多态和动态多态。

---

## 14. 一个更完整的泛型算法例子

```cpp
#include <concepts>
#include <cstddef>
#include <ranges>
#include <vector>

template <class T>
concept Number = std::integral<T> || std::floating_point<T>;

template <class R>
concept NumberRange =
    std::ranges::input_range<R> &&
    Number<std::ranges::range_value_t<R>>;

template <NumberRange R>
auto mean(const R& xs) {
    using T = std::ranges::range_value_t<R>;

    T sum{};
    std::size_t count = 0;

    for (const auto& x : xs) {
        sum += x;
        ++count;
    }

    if (count == 0) {
        return T{};
    }

    return sum / static_cast<T>(count);
}
```

使用：

```cpp
std::vector<double> xs{1.0, 2.0, 3.0};
auto m = mean(xs);
```

这个例子里：

* 算法不关心具体容器
* 只要求输入是数字 range
* 空 range 有定义好的行为

---

## 15. 常见误区

### 15.1 concepts 会让代码自动更快

不会。  
它主要改善接口约束和错误诊断。性能仍取决于代码结构和优化器。

### 15.2 concept 越细越好

不一定。  
过细会让接口僵硬，调用者很难满足。

### 15.3 concept 能替代单元测试

不能。  
它只能检查类型能力，不能验证业务逻辑。

### 15.4 所有模板都必须加 concept

内部小模板如果很清楚，可以不加。  
公共接口、错误难读的接口更值得加。

### 15.5 用 `same_as` 锁死具体类型

除非必须是这个类型，否则优先描述能力。

---

## 16. 一页总结

concepts 最重要的实践原则：

1. 优先用标准库已有 concept
2. 自定义 concept 描述最小必要能力
3. 公共泛型接口值得加约束
4. 不要用 concept 替代运行期检查
5. 不要过度约束到具体容器类型
6. concepts 适合静态多态，虚函数适合动态多态

一句话：

> concept 是把模板的“隐含要求”变成“显式接口”的工具。

---

# [21]常用标准库组件：format、chrono、filesystem与source_location

# 常用标准库组件：format、chrono、filesystem 与 source_location

时间：2026/05/08

> 关键词：`std::format`、`std::chrono`、`std::filesystem`、`std::source_location`、`std::bit`、随机数  
> 核心目标：把现代 C++ 标准库里最常用于工程代码的组件串起来，减少手写工具函数和平台相关代码。

---

## 1. 为什么要单独整理这些组件

很多 C++ 工程里会重复造这些小轮子：

* 字符串格式化
* 时间统计
* 路径拼接
* 文件遍历
* 日志行号
* 位操作
* 随机数

现代标准库已经提供了不少可用组件。  
掌握它们不一定会让代码更“高级”，但能让代码更少错、更统一、更容易跨平台。

---

## 2. `std::format`：类型安全格式化

传统 `printf` 容易出现格式和参数不匹配：

```cpp
std::printf("%d\n", "hello"); // 错误但可能编译过
```

C++20 提供 `std::format`：

```cpp
#include <format>
#include <string>

std::string msg = std::format("user={}, score={}", "alice", 95);
```

输出：

```text
user=alice, score=95
```

基本格式：

```cpp
auto a = std::format("{}", 42);
auto b = std::format("{:04}", 7);       // 0007
auto c = std::format("{:.2f}", 3.14159); // 3.14
auto d = std::format("{:<10}", "cpp");  // 左对齐
auto e = std::format("{:>10}", "cpp");  // 右对齐
```

注意：如果你的编译器/标准库版本还没完整支持 `std::format`，工程里常用 `{fmt}` 作为替代。

---

## 3. 自定义类型的格式化

可以给类型提供 formatter：

```cpp
#include <format>
#include <string>

struct Point {
    int x = 0;
    int y = 0;
};

template <>
struct std::formatter<Point> : std::formatter<std::string> {
    auto format(const Point& p, std::format_context& ctx) const {
        return std::formatter<std::string>::format(
            std::format("({}, {})", p.x, p.y),
            ctx
        );
    }
};

int main() {
    Point p{3, 4};
    auto s = std::format("point={}", p);
}
```

对于业务类型，建议优先提供明确的格式：

```cpp
auto s = std::format("id={}, name={}", user.id, user.name);
```

只有类型本身经常需要统一展示时，再专门写 formatter。

---

## 4. `std::chrono`：不要再裸写毫秒整数

坏接口：

```cpp
void set_timeout(int timeout_ms);
```

调用时容易搞错单位：

```cpp
set_timeout(5); // 5 ms 还是 5 s？
```

更好的接口：

```cpp
#include <chrono>

void set_timeout(std::chrono::milliseconds timeout);

set_timeout(std::chrono::seconds(5));
set_timeout(std::chrono::milliseconds(500));
```

`chrono` 把单位放进类型系统，能减少大量隐形 bug。

---

## 5. 计时优先用 `steady_clock`

测耗时不要用系统时间。  
系统时间可能被 NTP 或用户调整。

```cpp
#include <chrono>
#include <iostream>

class Timer {
public:
    Timer() : start_(clock::now()) {}

    double elapsed_ms() const {
        auto end = clock::now();
        std::chrono::duration<double, std::milli> d = end - start_;
        return d.count();
    }

private:
    using clock = std::chrono::steady_clock;
    clock::time_point start_;
};

int main() {
    Timer t;
    do_work();
    std::cout << "cost=" << t.elapsed_ms() << "ms\n";
}
```

常用选择：

* `steady_clock`：测耗时
* `system_clock`：表示日历时间、日志时间
* `high_resolution_clock`：不一定比前两者更适合，实际可能只是别名

---

## 6. chrono 字面量

```cpp
using namespace std::chrono_literals;

auto timeout = 500ms;
auto interval = 2s;
auto one_day = 24h;
```

可以写出更清楚的代码：

```cpp
std::this_thread::sleep_for(100ms);
```

如果在头文件里，不建议直接写：

```cpp
using namespace std::chrono_literals;
```

可以在函数内部使用，减少命名污染。

---

## 7. `std::filesystem::path`：跨平台路径拼接

不要手动拼路径分隔符：

```cpp
std::string full = dir + "/" + file;
```

用 `filesystem`：

```cpp
#include <filesystem>

namespace fs = std::filesystem;

fs::path dir = "logs";
fs::path file = "app.txt";
fs::path full = dir / file;
```

常用操作：

```cpp
fs::path p = "/tmp/demo.txt";

auto filename = p.filename();   // demo.txt
auto stem = p.stem();           // demo
auto ext = p.extension();       // .txt
auto parent = p.parent_path();  // /tmp
```

---

## 8. 创建目录和遍历文件

创建目录：

```cpp
#include <filesystem>

namespace fs = std::filesystem;

void ensure_dir(const fs::path& dir) {
    if (!fs::exists(dir)) {
        fs::create_directories(dir);
    }
}
```

遍历目录：

```cpp
#include <filesystem>
#include <iostream>

namespace fs = std::filesystem;

void list_cpp_files(const fs::path& root) {
    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        if (!entry.is_regular_file()) {
            continue;
        }

        if (entry.path().extension() == ".cpp") {
            std::cout << entry.path() << "\n";
        }
    }
}
```

注意：

* 文件系统操作可能抛异常
* 权限、符号链接、循环链接都要考虑
* 遍历大目录时不要默认全量递归

---

## 9. filesystem 的错误处理版本

如果不想用异常，可以传 `std::error_code`：

```cpp
#include <filesystem>
#include <system_error>

namespace fs = std::filesystem;

bool try_remove(const fs::path& p) {
    std::error_code ec;
    bool removed = fs::remove(p, ec);
    if (ec) {
        log_error(ec.message());
        return false;
    }
    return removed;
}
```

这和错误处理章节能接上：

* 异常适合少见失败
* `error_code` 适合你想显式处理每一步失败

---

## 10. `std::source_location`：日志自动带位置

C++20 的 `source_location` 可以捕获调用点文件、行号、函数名。

```cpp
#include <source_location>
#include <iostream>
#include <string_view>

void log(std::string_view msg,
         const std::source_location& loc = std::source_location::current()) {
    std::cout << loc.file_name() << ":" << loc.line()
              << " " << loc.function_name()
              << " - " << msg << "\n";
}

void f() {
    log("hello");
}
```

比宏更类型安全，也更容易封装。

注意：

```cpp
void log_impl(std::string_view msg,
              std::source_location loc);

void log(std::string_view msg,
         std::source_location loc = std::source_location::current()) {
    log_impl(msg, loc);
}
```

默认参数要放在最外层 API 上，才能捕获真正调用点。

---

## 11. `std::bit`：位操作不要手写太多

C++20 `<bit>` 提供常用位工具：

```cpp
#include <bit>
#include <cstdint>

static_assert(std::has_single_bit(8u));
static_assert(std::bit_width(8u) == 4);
static_assert(std::popcount(0b1011u) == 3);
```

常见用途：

```cpp
bool is_power_of_two(std::uint32_t x) {
    return std::has_single_bit(x);
}

std::uint32_t next_capacity(std::uint32_t n) {
    return std::bit_ceil(n);
}
```

比自己写位运算更不容易错，也更能表达意图。

---

## 12. `std::bit_cast`：安全表达按位转换

以前很多人用 `reinterpret_cast` 或 union 做位解释。  
C++20 提供 `std::bit_cast`：

```cpp
#include <bit>
#include <cstdint>

float f = 1.0f;
std::uint32_t bits = std::bit_cast<std::uint32_t>(f);
```

要求：

* 源类型和目标类型大小相同
* 类型通常应是 trivially copyable

它比直接乱用 `reinterpret_cast` 更安全、更清楚。

---

## 13. 随机数：不要用 `rand()`

现代 C++ 随机数由两部分组成：

* 引擎：生成随机位
* 分布：把随机位映射成目标分布

```cpp
#include <random>
#include <iostream>

int main() {
    std::random_device rd;
    std::mt19937 rng(rd());
    std::uniform_int_distribution<int> dist(1, 6);

    for (int i = 0; i < 5; ++i) {
        std::cout << dist(rng) << "\n";
    }
}
```

如果需要可复现测试，固定 seed：

```cpp
std::mt19937 rng(12345);
```

如果是安全随机数，标准库随机数通常不够，要用系统或密码学库提供的安全随机接口。

---

## 14. 一个小工具组合示例：扫描目录并打印报告

```cpp
#include <chrono>
#include <filesystem>
#include <format>
#include <iostream>
#include <source_location>

namespace fs = std::filesystem;

void log(std::string_view msg,
         const std::source_location& loc = std::source_location::current()) {
    std::cout << std::format("{}:{} {}\n",
                             loc.file_name(),
                             loc.line(),
                             msg);
}

std::size_t count_files(const fs::path& root, std::string_view ext) {
    std::size_t count = 0;

    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        if (entry.is_regular_file() && entry.path().extension() == ext) {
            ++count;
        }
    }

    return count;
}

int main() {
    auto start = std::chrono::steady_clock::now();

    fs::path root = "src";
    auto count = count_files(root, ".cpp");

    auto end = std::chrono::steady_clock::now();
    std::chrono::duration<double, std::milli> ms = end - start;

    log(std::format("found {} cpp files in {:.2f} ms", count, ms.count()));
}
```

这里组合了：

* `filesystem` 管路径和遍历
* `chrono` 测耗时
* `format` 构造消息
* `source_location` 自动带调用点

---

## 15. 常见误区

### 15.1 手写路径分隔符

跨平台路径用 `std::filesystem::path`，不要自己拼 `/` 或 `\`。

### 15.2 用 `system_clock` 测耗时

测耗时优先 `steady_clock`。

### 15.3 `string_view` 传给异步日志后再保存

异步日志如果晚点再格式化，`string_view` 可能已经悬空。  
跨线程保存时通常要复制成 `std::string`。

### 15.4 以为 `std::format` 所有环境都可用

不同标准库支持进度可能不同。  
工程里要用 CI 验证目标平台，必要时用 `{fmt}`。

### 15.5 随机测试每次都用随机 seed

测试失败后很难复现。  
测试用例建议记录 seed 或固定 seed。

---

## 16. 一页总结

现代标准库里最值得日常使用的组件：

1. `std::format`：类型安全格式化
2. `std::chrono`：把时间单位放进类型系统
3. `std::filesystem`：跨平台路径与文件操作
4. `std::source_location`：日志和诊断自动带调用点
5. `<bit>`：标准位操作工具
6. `<random>`：引擎 + 分布的随机数模型

一句话：

> 这些组件的价值在于减少自制小工具，让常见工程代码更清楚、更可移植、更容易测试。

---

# [22]依赖管理与包管理：FetchContent、vcpkg、Conan

# 依赖管理与包管理：FetchContent、vcpkg、Conan

时间：2026/05/08

> 关键词：CMake、FetchContent、find_package、vcpkg manifest、Conan 2、版本固定、可复现构建  
> 核心目标：理解 C++ 项目如何管理第三方库，避免“我机器上能编”的依赖混乱。

---

## 1. 为什么 C++ 依赖管理值得单独学

C++ 依赖管理比很多语言麻烦，常见原因是：

* 编译器和标准库 ABI 会影响二进制兼容
* Debug / Release 可能需要不同二进制
* 静态库、动态库、头文件库混在一起
* CMake target 传播 include path、宏、链接库
* 不同平台依赖安装方式不同
* 依赖版本不固定会导致构建不可复现

现代 C++ 工程通常围绕 CMake target 管依赖。  
包管理工具的最终目的也是让你能写：

```cmake
find_package(fmt CONFIG REQUIRED)
target_link_libraries(app PRIVATE fmt::fmt)
```

而不是到处手写 include path 和 library path。

---

## 2. 先分清三种依赖接入方式

### 2.1 系统已安装依赖

适合：

* 系统库
* 团队统一开发镜像
* Linux 发行版包

```cmake
find_package(OpenSSL REQUIRED)
target_link_libraries(app PRIVATE OpenSSL::SSL OpenSSL::Crypto)
```

优点：简单。  
缺点：版本和平台差异容易失控。

### 2.2 CMake 拉源码

适合：

* 小型依赖
* 测试库
* 纯 CMake 项目
* 需要和主项目一起构建

典型工具：`FetchContent`。

### 2.3 包管理器

适合：

* 依赖较多
* 跨平台
* 需要固定版本
* 需要预编译二进制或统一构建选项

常见工具：

* vcpkg
* Conan

---

## 3. CMake 依赖使用的核心：target

现代 CMake 里，依赖最好表现为 imported target：

```cmake
find_package(fmt CONFIG REQUIRED)

add_executable(app main.cpp)
target_link_libraries(app PRIVATE fmt::fmt)
```

`fmt::fmt` 这个 target 里通常带着：

* include 目录
* 编译定义
* 编译选项
* 链接库
* 传递依赖

不要写成：

```cmake
include_directories(/usr/local/include)
link_directories(/usr/local/lib)
target_link_libraries(app PRIVATE fmt)
```

这种写法会污染全局，且不容易跨平台。

---

## 4. FetchContent：配置期拉取源码

`FetchContent` 适合把第三方源码在 CMake configure 阶段引入。

```cmake
cmake_minimum_required(VERSION 3.20)
project(demo LANGUAGES CXX)

include(FetchContent)

FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG        10.2.1
)

FetchContent_MakeAvailable(fmt)

add_executable(app main.cpp)
target_link_libraries(app PRIVATE fmt::fmt)
```

`FetchContent_Declare()` 记录依赖来源。  
`FetchContent_MakeAvailable()` 让依赖可用，并尽量加入当前构建。

---

## 5. FetchContent 要固定版本

不要这样：

```cmake
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG        master
)
```

`master` 会变，今天能编不代表明天能编。

更好的写法：

```cmake
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG        10.2.1
)
```

更严谨时用 commit hash：

```cmake
FetchContent_Declare(
  fmt
  GIT_REPOSITORY https://github.com/fmtlib/fmt.git
  GIT_TAG        0c9fce2ffefecfdce794e1859584e25877b7b592
)
```

原则：

> 依赖版本必须可复现，不要让构建悄悄追随远端分支。

---

## 6. FetchContent 适合和不适合什么

适合：

* googletest
* 小型头文件库
* CMake 支持好的库
* 项目内工具库

不太适合：

* 依赖树很大的库
* 需要复杂系统依赖的库
* 多项目共享同一套二进制依赖
* 构建时间很敏感的大工程

原因是 `FetchContent` 通常把依赖纳入当前构建，依赖多了以后配置和编译时间会变重。

---

## 7. vcpkg manifest 模式

vcpkg 推荐项目用 `vcpkg.json` 描述依赖。

```json
{
  "name": "demo",
  "version-string": "0.1.0",
  "dependencies": [
    "fmt",
    "nlohmann-json"
  ]
}
```

在包含 `vcpkg.json` 的项目目录中安装：

```bash
vcpkg install
```

CMake 配置时使用 vcpkg toolchain：

```bash
cmake -S . -B build \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build build
```

CMakeLists：

```cmake
cmake_minimum_required(VERSION 3.20)
project(demo LANGUAGES CXX)

find_package(fmt CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

add_executable(app main.cpp)
target_link_libraries(app PRIVATE fmt::fmt nlohmann_json::nlohmann_json)
```

---

## 8. vcpkg features

有些包提供 feature：

```json
{
  "name": "demo",
  "version-string": "0.1.0",
  "dependencies": [
    {
      "name": "boost",
      "features": ["filesystem"]
    }
  ]
}
```

feature 用来控制可选组件。  
不要盲目打开所有 feature，否则依赖树会变大，构建时间也会变长。

---

## 9. vcpkg 版本固定和 registry

仅写：

```json
{
  "dependencies": ["fmt"]
}
```

不能完整表达“用哪一组端口版本”。  
工程上更可复现的做法是配合 baseline 或自己的 registry。

`vcpkg-configuration.json` 可以指定 registry 和 baseline：

```json
{
  "default-registry": {
    "kind": "git",
    "repository": "https://github.com/microsoft/vcpkg",
    "baseline": "7476f0d4e77d3333fbb249657df8251c28c4faae"
  }
}
```

思路和锁文件类似：

> 不只记录“我要 fmt”，还要记录“从哪一版依赖索引解析 fmt”。

---

## 10. Conan 2：用配置生成 CMake 依赖文件

Conan 2 常见方式是用 `conanfile.txt` 或 `conanfile.py` 描述依赖，并生成 CMake 所需文件。

一个简单 `conanfile.txt`：

```ini
[requires]
fmt/10.2.1
nlohmann_json/3.11.3

[generators]
CMakeDeps
CMakeToolchain

[layout]
cmake_layout
```

安装依赖：

```bash
conan install . --build=missing -s build_type=Release
```

配置 CMake：

```bash
cmake -S . -B build/Release \
  -DCMAKE_TOOLCHAIN_FILE=build/Release/generators/conan_toolchain.cmake \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/Release
```

CMakeLists：

```cmake
cmake_minimum_required(VERSION 3.20)
project(demo LANGUAGES CXX)

find_package(fmt CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

add_executable(app main.cpp)
target_link_libraries(app PRIVATE fmt::fmt nlohmann_json::nlohmann_json)
```

Conan 2 的 CMake 集成重点是：

* `CMakeToolchain` 生成 toolchain 文件
* `CMakeDeps` 生成 `find_package()` 能找到的配置文件
* CMakeLists 本身尽量不感知 Conan

---

## 11. Conan 用 `conanfile.py` 表达更复杂逻辑

如果依赖需要条件判断、选项、打包，就用 `conanfile.py`。

```python
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMakeDeps, cmake_layout

class DemoRecipe(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = (
        "fmt/10.2.1",
        "nlohmann_json/3.11.3",
    )

    def layout(self):
        cmake_layout(self)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()

        tc = CMakeToolchain(self)
        tc.generate()
```

适合：

* 条件依赖
* 自定义选项
* 需要发布包
* cross build
* tool requirements

---

## 12. FetchContent、vcpkg、Conan 怎么选

简单对比：

| 场景 | 更合适 |
| --- | --- |
| 小项目拉一个测试库 | FetchContent |
| 跨平台应用，依赖很多开源库 | vcpkg |
| 需要二进制包、私有包、复杂构建矩阵 | Conan |
| 公司内部 C++ 包生态 | Conan 或私有 vcpkg registry |
| 依赖是项目内源码模块 | `add_subdirectory` |

没有绝对答案。  
最关键的是团队统一一种主路径，不要每个依赖一种接入方式。

---

## 13. 依赖封装：不要让第三方库扩散到所有文件

坏模式：

```cpp
// 到处 include 第三方库头文件
#include <nlohmann/json.hpp>

void handle(const nlohmann::json& j);
```

更稳的边界：

```cpp
// config.h
struct Config {
    std::string host;
    int port = 0;
};

Config parse_config(std::string_view text);
```

```cpp
// config.cpp
#include "config.h"
#include <nlohmann/json.hpp>

Config parse_config(std::string_view text) {
    auto j = nlohmann::json::parse(text);
    return Config{
        .host = j.at("host").get<std::string>(),
        .port = j.at("port").get<int>(),
    };
}
```

好处：

* 第三方依赖集中在实现文件
* 以后替换 JSON 库成本低
* 编译依赖更少
* 公共 API 更稳定

---

## 14. CMake target 封装第三方依赖

可以把第三方库包在自己的库 target 后面：

```cmake
add_library(config config.cpp)
target_include_directories(config PUBLIC include)
target_link_libraries(config PRIVATE nlohmann_json::nlohmann_json)

add_executable(app main.cpp)
target_link_libraries(app PRIVATE config)
```

注意这里 JSON 库是 `PRIVATE`。  
如果 `config` 的 public header 没暴露 `nlohmann::json`，调用者就不需要知道它。

如果 public header 暴露了第三方类型：

```cpp
#include <nlohmann/json.hpp>

nlohmann::json to_json(const Config&);
```

那 CMake 就必须：

```cmake
target_link_libraries(config PUBLIC nlohmann_json::nlohmann_json)
```

依赖是否 `PUBLIC`，取决于它是否出现在你的公开接口里。

---

## 15. 版本策略

依赖版本管理的几个原则：

1. 应用项目应固定版本
2. 库项目应谨慎扩大版本范围
3. 不要默认追随 `master/main`
4. 升级依赖要有测试
5. 安全更新要单独跟踪
6. 记录每次升级原因和影响

示例升级记录：

```text
fmt 10.1.1 -> 10.2.1
reason: fix compiler warning on Clang 17
checked: unit tests, sanitizer build, linux/macOS CI
impact: no public API change
```

依赖升级不是“顺手改一下版本号”，它是工程变更。

---

## 16. 私有库和内部包

团队内部库常见做法：

* Git submodule
* FetchContent 指向内部仓库
* vcpkg custom registry
* Conan remote
* monorepo 里 `add_subdirectory`

选择时看：

* 是否需要独立版本
* 是否需要二进制缓存
* 是否跨多个项目复用
* 是否要支持多个编译器和平台
* 是否需要访问控制

小团队可以先简单，别一开始就搭很重的平台。  
但只要项目多起来，就要尽早统一依赖入口。

---

## 17. 一个推荐的 CMake 工程结构

```text
demo/
  CMakeLists.txt
  vcpkg.json 或 conanfile.txt
  include/
    demo/config.h
  src/
    config.cpp
    main.cpp
  tests/
    config_test.cpp
```

顶层 CMake：

```cmake
cmake_minimum_required(VERSION 3.20)
project(demo LANGUAGES CXX)

find_package(fmt CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

add_library(demo_config src/config.cpp)
target_include_directories(demo_config PUBLIC include)
target_link_libraries(demo_config
  PRIVATE
    nlohmann_json::nlohmann_json
)

add_executable(demo_app src/main.cpp)
target_link_libraries(demo_app
  PRIVATE
    demo_config
    fmt::fmt
)
```

main.cpp：

```cpp
#include <demo/config.h>
#include <fmt/format.h>

int main() {
    auto cfg = parse_config(R"({"host":"127.0.0.1","port":8080})");
    fmt::print("{}:{}\n", cfg.host, cfg.port);
}
```

---

## 18. 常见误区

### 18.1 依赖版本不固定

构建不可复现，问题会在未来某一天突然出现。

### 18.2 到处写 include path

现代 CMake 应该靠 target 传播依赖信息。

### 18.3 public header 暴露第三方类型

这会让第三方库变成你的 API 一部分，替换成本很高。

### 18.4 Debug 链接 Release 依赖

有些平台和库会出 ABI 或运行时问题。  
要让包管理器按 build type 安装匹配依赖。

### 18.5 混用多套包管理器且没有边界

FetchContent、vcpkg、Conan 可以共存，但要有明确规则。  
例如测试库用 FetchContent，第三方运行库统一用 vcpkg。

---

## 19. 一页总结

依赖管理的核心原则：

1. CMake 里优先使用 target
2. 能 `find_package()` 就不要手写路径
3. 版本要固定，构建要可复现
4. 第三方类型尽量别扩散到公共 API
5. 小依赖可用 FetchContent
6. 跨平台应用可考虑 vcpkg
7. 私有包和复杂构建矩阵可考虑 Conan

一句话：

> 依赖管理不是把库下载下来，而是让依赖版本、构建选项、链接方式和 API 边界都可控。

---

## 20. 参考资料

1. CMake FetchContent  
   <https://cmake.org/cmake/help/latest/module/FetchContent.html>

2. vcpkg manifest mode  
   <https://learn.microsoft.com/en-us/vcpkg/concepts/manifest-mode>

3. Conan 2 CMake integration  
   <https://docs.conan.io/2/integrations/cmake.html>

4. Conan 2 CMakeDeps  
   <https://docs.conan.io/2/reference/tools/cmake/cmakedeps.html>

---

# 单例子模式

# 单例模式

时间：2026/05/03

> 关键词：Singleton、Meyers Singleton、线程安全初始化、`std::call_once`、初始化失败、重复初始化、析构顺序  
> 核心目标：掌握 C++ 里最常见的单例写法，并能回答面试里关于线程安全、初始化失败和生命周期的问题。

---

## 1. 单例模式在解决什么问题

单例模式想解决的是：

* 某个类在整个进程里只需要一个实例
* 所有地方访问的是同一个对象
* 对象创建和生命周期由类自己控制

常见场景：

* 日志系统
* 配置管理
* 资源管理器
* 全局 ID 生成器
* 游戏里的全局服务入口

但要注意：

> 单例本质上是一种“受控的全局对象”，不要因为方便就到处用。

如果一个对象只是普通依赖，优先考虑构造函数传参、依赖注入或明确的所有权关系。

---

## 2. C++11 后最推荐的基础写法

最常见、最推荐的是函数局部静态变量，也叫 Meyers Singleton。
在同一个进程中，同一个函数内的 static 局部变量只初始化一次。

```cpp
class Singleton {
public:
    static Singleton& instance() {
        static Singleton inst;
        return inst;
    }

    void do_something() {
        // ...
    }

private:
    Singleton() = default;
    ~Singleton() = default;

    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;

    Singleton(Singleton&&) = delete;
    Singleton& operator=(Singleton&&) = delete;
};
```

调用：

```cpp
Singleton::instance().do_something();
```

这段代码的重点：

* 构造函数私有，外部不能随便创建
* 拷贝和移动都删除，避免复制出第二个实例
* `instance()` 里用 `static Singleton inst`
* C++11 起，函数局部静态变量初始化是线程安全的

---

## 3. 为什么不推荐手写裸指针单例

老式写法经常是：

```cpp
class Singleton {
public:
    static Singleton* instance() {
        if (ptr_ == nullptr) {
            ptr_ = new Singleton();
        }
        return ptr_;
    }

private:
    Singleton() = default;
    static Singleton* ptr_;
};
```

问题很多：

* 多线程下可能重复创建
* 需要手动释放，容易内存泄漏
* 释放时机难控制
* 如果加锁写不好，还可能产生性能或竞态问题

所以现代 C++ 里，基础单例优先用函数局部静态变量。

---

## 4. 面试常问：单例是否线程安全

如果是 C++11 及之后的 Meyers Singleton：

```cpp
static Singleton inst;
```

初始化本身是线程安全的。

也就是说：

* 多个线程同时第一次调用 `instance()`
* 只会有一个线程真正执行构造
* 其他线程会等待初始化完成

但是要分清楚：

> 单例对象的“初始化线程安全”不等于“对象内部所有方法都线程安全”。

例如：

```cpp
class Counter {
public:
    static Counter& instance() {
        static Counter c;
        return c;
    }

    void add() {
        ++value_;
    }

private:
    int value_ = 0;
};
```

这里 `Counter` 的创建是线程安全的，但多个线程同时调用 `add()` 仍然有数据竞争。

如果内部状态会被并发修改，仍然需要：

* `std::mutex`
* `std::atomic`
* 或者更清晰的并发设计

---

## 5. 面试常问：单例初始化失败怎么办

初始化失败通常指构造函数里抛异常。

```cpp
#include <stdexcept>

class Config {
public:
    static Config& instance() {
        static Config cfg;
        return cfg;
    }

private:
    Config() {
        if (!load_file()) {
            throw std::runtime_error("load config failed");
        }
    }

    bool load_file() {
        return false;
    }
};
```

如果 `static Config cfg;` 初始化时抛异常：

* 当前这次 `instance()` 调用会把异常抛出去
* 这个局部静态对象不会被视为初始化完成
* 下一次再调用 `instance()` 时，会重新尝试初始化

也就是说，C++ 的局部静态变量初始化失败后不是永久失败，而是下次会重试。

面试回答可以这样说：

> C++11 的函数局部静态变量初始化是线程安全的；如果构造过程抛异常，本次初始化失败，异常向外传播，下次进入该声明时会再次尝试初始化。

### 5.1 初始化失败要不要重试

这取决于业务语义。

适合重试的情况：

* 配置文件短暂不可用
* 网络资源暂时失败
* 外部服务可能恢复

不适合无限重试的情况：

* 程序启动参数错误
* 必要文件不存在
* 配置格式根本不合法

工程里可以选择：

* 直接让异常向外抛，启动失败
* 在外层捕获异常并打印日志
* 提供显式 `init()`，让初始化失败变成可控返回值

---

## 6. 面试常问：重复初始化怎么办

“重复初始化”有两种情况。

### 6.1 多次调用 `instance()`

对于 Meyers Singleton：

```cpp
auto& a = Singleton::instance();
auto& b = Singleton::instance();
```

这不会重复初始化。

第一次调用时构造对象，后面所有调用都返回同一个对象引用。

### 6.2 显式 `init()` 被调用多次

如果单例需要配置参数，就容易出现重复初始化问题。

错误倾向是：

```cpp
Logger::instance("a.log");
Logger::instance("b.log");
```

第一次和第二次传了不同参数，到底该听谁的？这会让语义混乱。

更清晰的方式是拆成：

* `init(config)`：启动阶段显式初始化
* `instance()`：使用阶段只获取对象

示例：

```cpp
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>

class Logger {
public:
    static void init(std::string file) {
        std::lock_guard<std::mutex> lk(mutex_);

        if (initialized_) {
            throw std::runtime_error("Logger already initialized");
        }

        file_ = std::move(file);
        initialized_ = true;
    }

    static Logger& instance() {
        if (!initialized_) {
            throw std::runtime_error("Logger not initialized");
        }

        static Logger logger;
        return logger;
    }

private:
    Logger() = default;

    inline static std::mutex mutex_;
    inline static bool initialized_ = false;
    inline static std::string file_;
};
```

这类写法的核心是：

* 重复初始化要么直接忽略，要么明确报错
* 不要让不同配置悄悄覆盖已有配置
* 初始化和使用阶段要有清晰边界

不过上面这版还有个细节：`instance()` 读取 `initialized_` 时没有加锁。更严谨的工程代码要么也加锁，要么用 `std::atomic<bool>`，要么使用 `std::call_once`。

---

## 7. 使用 `std::call_once` 的写法

如果不想依赖局部静态变量，或者要做更复杂的初始化，可以用 `std::call_once`。

```cpp
#include <memory>
#include <mutex>

class Singleton {
public:
    static Singleton& instance() {
        std::call_once(flag_, [] {
            ptr_ = std::unique_ptr<Singleton>(new Singleton());
        });
        return *ptr_;
    }

private:
    Singleton() = default;

    inline static std::once_flag flag_;
    inline static std::unique_ptr<Singleton> ptr_;
};
```

特点：

* 初始化逻辑只会成功执行一次
* 多线程同时调用时，只有一个线程执行初始化
* 如果初始化函数抛异常，`once_flag` 不会被标记完成，下次会继续尝试

不过对于普通单例，Meyers Singleton 更简洁。

---

## 8. 面试常问：双重检查锁为什么容易出问题

经典写法类似：

```cpp
if (ptr == nullptr) {
    std::lock_guard<std::mutex> lk(mutex);
    if (ptr == nullptr) {
        ptr = new Singleton();
    }
}
```

它叫 Double-Checked Locking。

问题在于：

* 对象构造和指针赋值涉及内存可见性
* 没有正确的原子操作和内存序，其他线程可能看到“指针非空但对象还没完全构造好”
* 写对很麻烦，写错很隐蔽

现代 C++ 面试里可以直接说：

> 不建议手写双重检查锁。C++11 后用函数局部静态变量或 `std::call_once` 更简单、更安全。

---

## 9. 面试常问：单例什么时候销毁

Meyers Singleton 的对象是函数局部静态变量：

```cpp
static Singleton inst;
```

它会在程序结束时自动析构。

但这里有一个经典问题：

> 静态对象析构顺序不容易控制。

如果多个全局对象或单例互相依赖，程序退出时可能出现：

1. 单例 A 已经析构
2. 单例 B 的析构函数里还想用 A
3. 访问已经销毁的对象，产生未定义行为

应对方式：

* 避免单例之间在析构阶段互相调用
* 把释放逻辑放到明确的 `shutdown()` 阶段
* 对某些进程级对象，接受“不主动析构”，让操作系统在进程退出时回收

有些日志系统会故意写成泄漏式单例：

```cpp
static Logger& instance() {
    static Logger* logger = new Logger();
    return *logger;
}
```

这样对象不会在程序退出时自动析构，可以避开析构顺序问题。

但代价是：

* 内存检查工具会看到泄漏
* 资源释放不够优雅
* 不适合所有场景

所以这是工程取舍，不是默认推荐写法。

---

## 10. 面试常问：单例能不能带参数

可以，但要小心。

不推荐这样：

```cpp
Config& c1 = Config::instance("dev.yaml");
Config& c2 = Config::instance("prod.yaml");
```

因为第二次调用传入的参数通常不会生效，容易误导调用方。

更推荐：

```cpp
Config::init("dev.yaml");
auto& config = Config::instance();
```

也就是：

* 初始化参数只在启动阶段传一次
* 之后使用时不再传参数
* 重复初始化时明确报错

---

## 11. 单例的优缺点

优点：

* 使用方便
* 保证进程内只有一个实例
* 适合管理全局唯一资源

缺点：

* 本质上是全局状态
* 容易隐藏依赖关系
* 测试时不好替换
* 生命周期复杂时容易踩坑
* 多线程下内部状态仍然需要额外保护

面试里不要只说“单例简单方便”，最好补一句：

> 单例适合管理少数真正全局唯一的服务，但滥用会让依赖关系变隐式，降低可测试性。

---

## 12. 常见面试问题速答

### 12.1 C++ 单例怎么写最简单安全

用函数局部静态变量：

```cpp
static Singleton& instance() {
    static Singleton inst;
    return inst;
}
```

C++11 后初始化线程安全。

### 12.2 如何防止创建多个实例

* 构造函数私有
* 删除拷贝构造
* 删除拷贝赋值
* 删除移动构造
* 删除移动赋值

### 12.3 初始化失败怎么办

构造函数抛异常时，本次初始化失败，异常向外传播；下一次调用 `instance()` 会再次尝试初始化。

如果失败不可恢复，可以在程序启动阶段捕获异常并直接终止启动。

### 12.4 重复初始化怎么办

如果只是多次调用 `instance()`，不会重复初始化。

如果是显式 `init(config)` 被调用多次，要明确策略：

* 要么幂等，重复相同配置直接返回
* 要么报错
* 不要悄悄覆盖已有配置

### 12.5 单例对象内部方法一定线程安全吗

不一定。

单例初始化线程安全，只代表对象创建过程安全。对象内部如果有共享可变状态，仍然要自己加锁或使用原子变量。

### 12.6 单例和全局变量有什么区别

单例可以控制创建时机、禁止复制、封装访问入口。  
但它仍然带有全局状态的缺点。

---

## 13. 一页总结

现代 C++ 写单例优先记住：

1. 用函数局部静态变量实现基础单例
2. 私有构造，删除拷贝和移动
3. C++11 后局部静态变量初始化线程安全
4. 初始化失败抛异常后，下次调用会重试
5. 重复初始化要有明确策略
6. 单例创建安全不等于内部方法线程安全
7. 小心析构顺序和隐藏依赖

如果只记一句：

> 单例不是“到处方便访问”的借口，而是“进程内确实只应该有一个实例”的受控设计。