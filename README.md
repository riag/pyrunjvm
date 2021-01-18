# pyrunjvm
以 debug 模式启动 jvm， 并启动常见应用服务，目前支持通过 tomcat 容器来启动 exploded war , 下一步要支持启动多个 spring boot flat jar 包

## 原因
  在 intellij/Eclispe 等 IDE 里可以很方便通过 tomcat 容器来启动服务, 这样就可以很方便调试；
但这样做法有个缺点，tomcat 服务运行时间一长，就会影响到 IDE 的使用，出现 IDE 卡顿等，严重影响代码开发。

所以开发了这个工具，可以在命令行里方便启动 tomcat 服务，需要调试时，可以在 IDE 里使用 remote debug 来调试


## 使用

### 安装
 `TODO`

### 配置文件
  配置文件 `.pyrunjvm.toml` 定义了如何运行服务以及默认环境变量,
  因为每个用户的工具路径或者端口都不一样的，pyrunjvm 是通过定义环境变量来更改这些配置
  可在系统的环境变量里定义，或者在当前目录下建立配置文件 `.env` 来定义具体的环境变量

  在项目的根目录下新建文件 `.pyrunjvm.toml`, 下面是一个配置文件的例子
  ```
app_type = "tomcat"

[build]
clear_cmds = []
build_cmds = [
    "${GRADLE_BIN} explodedWar",
]

[[projects]]
context_path = "test-mgr"
exploded_war_path = "${WORK_DIR}/test-mgr/build/exploded"

[[projects]]
context_path = "test-api"
exploded_war_path = "${WORK_DIR}/test-api/build/exploded"

# default env
[env]
JVM_DEBUG_PORT = 50899
TOMCAT_PORT = 8080
GRADLE_BIN = "gradle"
JAVA_BIN = "java"

  ```

  环境变量配置文件 `.env` 例子

  ```
JVM_DEBUG_PORT = 50859
TOMCAT_PORT = 8080
GRADLE_BIN = "gradle"

GRADLE_BIN = "G:\\devel\\gradle-5.1.1\\bin\\gradle.bat"
JAVA_BIN="C:\\Users\\riag\\.jabba\\jdk\\zulu@1.8\\bin\\java.exe"
TOMCAT_HOME="G:\\devel\\apache-tomcat-8.5.16"
 
  ```

  ### 运行
  在命令行里 cd 到项目的根目录下，然后直接执行 `pyrunjvm` 命令就可以
