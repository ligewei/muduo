// Keep regression checks enabled in Release builds too.
#undef NDEBUG
#include "muduo/base/AsyncLogging.h"

#include <assert.h>
#include <glob.h>
#include <stdlib.h>
#include <unistd.h>

#include <fstream>
#include <iterator>

int main()
{
  // Isolate the generated log files from other tests and existing user logs.
  char directory[] = "/tmp/muduo-async-shutdown-XXXXXX";
  char* path = ::mkdtemp(directory);
  assert(path);
  int result = ::chdir(path);
  assert(result == 0);

  for (int i = 0; i < 20; ++i)
  {
    const muduo::string basename = "shutdown-" + std::to_string(i);
    const muduo::string message = "message before immediate stop\n";
    {
      muduo::AsyncLogging log(basename, 1024*1024, 1);
      log.start();
      log.append(message.data(), static_cast<int>(message.size()));
      log.stop();
    }

    glob_t files = {};
    result = ::glob((basename + ".*.log").c_str(), 0, NULL, &files);
    assert(result == 0);
    assert(files.gl_pathc == 1);
    std::ifstream input(files.gl_pathv[0]);
    const muduo::string contents((std::istreambuf_iterator<char>(input)),
                                std::istreambuf_iterator<char>());
    assert(contents == message);
    input.close();
    result = ::unlink(files.gl_pathv[0]);
    assert(result == 0);
    ::globfree(&files);
  }

  result = ::chdir("/");
  assert(result == 0);
  result = ::rmdir(path);
  assert(result == 0);
}
