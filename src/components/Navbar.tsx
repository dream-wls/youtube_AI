import React from 'react';

const Navbar = () => {
  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    element?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <nav className="bg-white shadow-lg fixed w-full top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <button 
            onClick={() => scrollToSection('home')} 
            className="text-xl font-bold"
          >
            我的博客
          </button>
          <div className="flex space-x-4">
            <button 
              onClick={() => scrollToSection('posts')}
              className="hover:text-gray-600"
            >
              文章
            </button>
            <button 
              onClick={() => scrollToSection('categories')}
              className="hover:text-gray-600"
            >
              分类
            </button>
            <button 
              onClick={() => scrollToSection('about')}
              className="hover:text-gray-600"
            >
              关于
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar; 