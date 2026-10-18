(function_def body: (parenthesized "(" (_)* @function.inside ")")) @function.around
(section body: (section_body) @class.inside) @class.around
(comment)+ @comment.around
